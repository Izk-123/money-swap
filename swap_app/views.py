from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse_lazy
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.messages.views import SuccessMessageMixin
from django.views.generic import TemplateView, CreateView, ListView, DetailView, UpdateView, View
from django.http import JsonResponse, HttpResponseForbidden
from django.utils.crypto import get_random_string
from django.views.decorators.csrf import csrf_exempt
from django.db import transaction
from django.db.models import Sum, Q, Count
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone
from datetime import datetime, timedelta
import json
from math import radians, sin, cos, sqrt, atan2

from .models import User, Account, SwapRequest, Agent, Notification, TransactionLog, AgentWallet
from .forms import *

# Mixins
class ClientRequiredMixin(UserPassesTestMixin):
    def test_func(self):
        return self.request.user.is_authenticated and self.request.user.role == 'client'

class AgentRequiredMixin(UserPassesTestMixin):
    def test_func(self):
        return self.request.user.is_authenticated and self.request.user.role == 'agent'

# Public Views
class HomeView(TemplateView):
    template_name = 'swap_app/home.html'

class RegisterView(SuccessMessageMixin, CreateView):
    model = User
    form_class = CustomUserCreationForm
    template_name = 'swap_app/register.html'
    success_url = reverse_lazy('login')
    success_message = "Account created successfully! Please login."
    
    def form_valid(self, form):
        response = super().form_valid(form)
        if self.object.role == 'agent':
            Agent.objects.create(user=self.object)
        return response

# Dashboard Views
class DashboardView(LoginRequiredMixin, TemplateView):
    template_name = 'swap_app/dashboard.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        
        # Get unread notifications
        context['notifications'] = Notification.objects.filter(
            user=user, 
            is_read=False
        ).order_by('-created_at')[:10]
        
        if user.role == 'client':
            swaps = SwapRequest.objects.filter(client=user)
            context.update({
                'total_swaps': swaps.count(),
                'pending_swaps': swaps.filter(status='PENDING').count(),
                'active_swaps': swaps.filter(status__in=['ACCEPTED', 'RESERVED']).count(),
                'recent_swaps': swaps.order_by('-created_at')[:5]
            })
            
        elif user.role == 'agent':
            agent = getattr(user, 'agent', None)
            if agent:
                agent_swaps = agent.swap_requests.all()
                context.update({
                    'agent': agent,
                    'pending_requests': agent_swaps.filter(status='PENDING').count(),
                    'active_swaps': agent_swaps.filter(status__in=['ACCEPTED', 'RESERVED', 'PAID_BANK']).count(),
                    'recent_swaps': agent_swaps.order_by('-created_at')[:5]
                })
        
        elif user.role == 'admin':
            context.update({
                'total_users': User.objects.count(),
                'total_agents': Agent.objects.filter(verified=True).count(),
                'total_swaps': SwapRequest.objects.count(),
                'pending_verification': Agent.objects.filter(verified=False).count(),
            })
        
        return context

# Agent Views
class AgentListView(LoginRequiredMixin, ListView):
    model = Agent
    template_name = 'swap_app/agent_list.html'
    context_object_name = 'agents'
    
    def get_queryset(self):
        return Agent.objects.filter(
            verified=True,
            is_online=True
        ).select_related('user').annotate(
            completed_swaps=Count('swap_requests', filter=Q(swap_requests__status='COMPLETE'))
        ).order_by('-rating', '-completed_swaps')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        
        context['client_location'] = user.location_address
        context['client_has_location'] = user.has_location
        
        if user.has_location:
            context['client_lat'] = float(user.location_lat)
            context['client_lng'] = float(user.location_lng)
        
        agents_data = []
        for agent in context['agents']:
            if agent.user.has_location:
                agents_data.append({
                    'id': agent.id,
                    'username': agent.user.username,
                    'lat': float(agent.user.location_lat),
                    'lng': float(agent.user.location_lng),
                    'address': agent.user.location_address,
                    'rating': agent.rating,
                    'float_mpamba': float(agent.float_mpamba),
                    'float_airtel': float(agent.float_airtel),
                    'is_online': agent.is_online,
                    'completed_swaps': getattr(agent, 'completed_swaps', 0),
                })
        
        context['agents_data_json'] = json.dumps(agents_data)
        context['google_maps_api_key'] = settings.GOOGLE_MAPS_API_KEY
        
        return context

class CreateSwapView(LoginRequiredMixin, SuccessMessageMixin, CreateView):
    model = SwapRequest
    form_class = SwapRequestForm
    template_name = 'swap_app/create_swap.html'
    success_message = "Swap request sent to agent!"
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        agent_id = self.request.POST.get('agent_id')
        if agent_id:
            kwargs['initial'] = {'agent': agent_id}
        return kwargs
    
    def form_valid(self, form):
        try:
            with transaction.atomic():
                swap = form.save(commit=False)
                swap.client = self.request.user
                swap.reference = 'SWAP-' + get_random_string(10).upper()
                
                # FIXED: Use Decimal for calculations
                from decimal import Decimal
                
                total_fee = swap.amount * Decimal('0.006')
                swap.platform_fee = (total_fee * Decimal('0.25')).quantize(Decimal('0.01'))
                swap.agent_fee = (total_fee * Decimal('0.75')).quantize(Decimal('0.01'))
                
                # Validate agent selection
                if not swap.agent:
                    form.add_error('agent', 'Please select an agent')
                    return self.form_invalid(form)
                
                # Check if agent has sufficient float
                if swap.to_service == 'TNM' and swap.agent.float_mpamba < swap.amount:
                    form.add_error(None, f'Selected agent has insufficient TNM Mpamba float. Available: MWK {swap.agent.float_mpamba}')
                    return self.form_invalid(form)
                elif swap.to_service == 'AIRTEL' and swap.agent.float_airtel < swap.amount:
                    form.add_error(None, f'Selected agent has insufficient Airtel Money float. Available: MWK {swap.agent.float_airtel}')
                    return self.form_invalid(form)
                
                swap.save()
                
                # Create notification for agent
                Notification.objects.create(
                    user=swap.agent.user,
                    swap_request=swap,
                    type='swap_request',
                    message=f"New swap request: MWK {swap.amount} from {swap.client.username}"
                )
                
                self.send_agent_notification(swap)
                
                TransactionLog.objects.create(
                    swap_request=swap,
                    type='SWAP_REQUEST_SENT',
                    payload={
                        'agent_id': swap.agent.id,
                        'amount': float(swap.amount),
                        'client_location': self.request.user.location_address,
                    }
                )
                
                # Set the object for get_success_url
                self.object = swap
                
            return super().form_valid(form)
            
        except Exception as e:
            # Log the error and return form invalid
            print(f"Error creating swap: {e}")
            form.add_error(None, f'Error creating swap: {str(e)}')
            return self.form_invalid(form)
    
    def form_invalid(self, form):
        """Handle invalid form submission"""
        print("Form invalid with errors:", form.errors)
        return super().form_invalid(form)
    
    def send_agent_notification(self, swap):
        try:
            subject = f"New Swap Request - {swap.reference}"
            message = f"""
            Hello {swap.agent.user.username},
            
            You have a new swap request from {swap.client.username}:
            
            Amount: MWK {swap.amount}
            From: {swap.get_from_service_display()}
            To: {swap.get_to_service_display()}
            Recipient: {swap.dest_number}
            
            Client Commission: MWK {swap.agent_fee}
            
            Please respond within 15 minutes.
            
            Login to your dashboard to accept or reject.
            
            Best regards,
            MoneySwap Team
            """
            
            send_mail(
                subject,
                message,
                settings.DEFAULT_FROM_EMAIL,
                [swap.agent.user.email],
                fail_silently=True,
            )
        except Exception as e:
            print(f"Failed to send email: {e}")
    
    def get_success_url(self):
        """Safe success URL that doesn't rely on self.object"""
        if hasattr(self, 'object') and self.object and self.object.pk:
            return reverse_lazy('swap_detail', kwargs={'pk': self.object.pk})
        else:
            # Fallback to swap list if object isn't available
            return reverse_lazy('client_swaps')

class AgentResponseView(LoginRequiredMixin, View):
    def post(self, request, pk):
        swap = get_object_or_404(SwapRequest, pk=pk, agent__user=request.user)
        form = AgentResponseForm(request.POST)
        
        if form.is_valid():
            action = form.cleaned_data['action']
            reason = form.cleaned_data['reason']
            
            with transaction.atomic():
                if action == 'accept':
                    swap.status = 'ACCEPTED'
                    message = f"Agent {request.user.username} accepted your swap request"
                    notification_type = 'swap_accepted'
                else:
                    swap.status = 'REJECTED'
                    message = f"Agent {request.user.username} rejected your swap request"
                    notification_type = 'swap_rejected'
                    if reason:
                        message += f". Reason: {reason}"
                
                swap.agent_response_at = timezone.now()
                swap.save()
                
                Notification.objects.create(
                    user=swap.client,
                    swap_request=swap,
                    type=notification_type,
                    message=message
                )
                
                TransactionLog.objects.create(
                    swap_request=swap,
                    type=f'AGENT_{action.upper()}',
                    payload={'reason': reason}
                )
                
                return JsonResponse({'success': True})
        
        return JsonResponse({'success': False, 'error': 'Invalid form'})

# Client Views
class ClientSwapRequestsView(LoginRequiredMixin, ClientRequiredMixin, ListView):
    model = SwapRequest
    template_name = 'swap_app/swap_list.html'
    context_object_name = 'swaps'
    
    def get_queryset(self):
        return SwapRequest.objects.filter(client=self.request.user).order_by('-created_at')

# Account Management
class AccountListView(LoginRequiredMixin, ListView):
    model = Account
    template_name = 'swap_app/accounts.html'
    context_object_name = 'accounts'
    
    def get_queryset(self):
        return Account.objects.filter(user=self.request.user, is_active=True)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form'] = AccountForm()
        return context

class AccountCreateView(LoginRequiredMixin, SuccessMessageMixin, CreateView):
    model = Account
    form_class = AccountForm
    success_message = "Account added successfully!"
    
    def form_valid(self, form):
        form.instance.user = self.request.user
        return super().form_valid(form)
    
    def get_success_url(self):
        return reverse_lazy('my_accounts')
    
class DeactivateAccountView(LoginRequiredMixin, View):
    def post(self, request, pk):
        account = get_object_or_404(Account, pk=pk, user=request.user)
        account.is_active = False
        account.save()
        messages.success(request, f"{account.get_account_type_display()} account deactivated.")
        return redirect('my_accounts')

class ActivateAccountView(LoginRequiredMixin, View):
    def post(self, request, pk):
        account = get_object_or_404(Account, pk=pk, user=request.user)
        account.is_active = True
        account.save()
        messages.success(request, f"{account.get_account_type_display()} account activated.")
        return redirect('my_accounts')

class EditAccountView(LoginRequiredMixin, UpdateView):
    model = Account
    form_class = AccountForm
    template_name = 'swap_app/accounts.html'
    
    def get_queryset(self):
        return Account.objects.filter(user=self.request.user)
    
    def form_valid(self, form):
        messages.success(self.request, "Account updated successfully!")
        return super().form_valid(form)
    
    def get_success_url(self):
        return reverse_lazy('my_accounts')

# Swap Management
class SwapDetailView(LoginRequiredMixin, DetailView):
    model = SwapRequest
    template_name = 'swap_app/swap_detail.html'
    context_object_name = 'swap'
    
    def get_queryset(self):
        user = self.request.user
        if user.role == 'client':
            return SwapRequest.objects.filter(client=user)
        elif user.role == 'agent':
            return SwapRequest.objects.filter(agent__user=user)
        return SwapRequest.objects.all()

class UploadProofView(LoginRequiredMixin, UpdateView):
    model = SwapRequest
    form_class = ProofUploadForm
    template_name = 'swap_app/upload_proof.html'
    context_object_name = 'swap'  # Add this line
    
    def get_queryset(self):
        return SwapRequest.objects.filter(client=self.request.user, status='ACCEPTED')
    
    def form_valid(self, form):
        swap = form.save(commit=False)
        swap.status = 'PAID_BANK'
        swap.save()
        
        TransactionLog.objects.create(
            swap_request=swap,
            type='BANK_PROOF_UPLOADED',
            payload={'note': 'Client uploaded bank deposit proof'}
        )
        return redirect('swap_detail', pk=swap.pk)

class AgentSendView(LoginRequiredMixin, View):
    def post(self, request, pk):
        swap = get_object_or_404(SwapRequest, pk=pk, agent__user=request.user)
        txid = request.POST.get('txid', '').strip()
        
        if txid:
            swap.agent_tx_id = txid
            swap.status = 'SENT_WALLET'
            swap.save()
            
            TransactionLog.objects.create(
                swap_request=swap,
                type='WALLET_SENT',
                provider_tx_id=txid,
                payload={'note': 'Agent marked wallet payment as sent'}
            )
        
        return redirect('swap_detail', pk=swap.pk)

class CompleteSwapView(LoginRequiredMixin, View):
    def post(self, request, pk):
        swap = get_object_or_404(SwapRequest, pk=pk, client=request.user)
        swap.status = 'COMPLETE'
        swap.save()
        
        TransactionLog.objects.create(
            swap_request=swap,
            type='CLIENT_CONFIRMED',
            payload={'note': 'Client confirmed receipt of wallet funds'}
        )
        return redirect('swap_detail', pk=swap.pk)

# Agent Dashboard Views
class AgentDashboardView(LoginRequiredMixin, AgentRequiredMixin, TemplateView):
    template_name = 'swap_app/agent_dashboard.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        agent = self.request.user.agent
        swaps = agent.swap_requests.all()
        
        today = datetime.now().date()
        week_ago = today - timedelta(days=7)
        month_ago = today - timedelta(days=30)
        
        weekly_earnings = swaps.filter(
            status='COMPLETE',
            created_at__gte=week_ago
        ).aggregate(Sum('agent_fee'))['agent_fee__sum'] or 0
        
        monthly_earnings = swaps.filter(
            status='COMPLETE', 
            created_at__gte=month_ago
        ).aggregate(Sum('agent_fee'))['agent_fee__sum'] or 0
        
        context.update({
            'agent': agent,
            'swaps': swaps.order_by('-created_at'),
            'weekly_earnings': weekly_earnings,
            'monthly_earnings': monthly_earnings,
            'pending_swaps': swaps.filter(status='PENDING').count(),
            'awaiting_send': swaps.filter(status='PAID_BANK').count(),
            'success_rate': self.calculate_success_rate(swaps),
        })
        return context
    
    def calculate_success_rate(self, swaps):
        total = swaps.count()
        if total == 0:
            return 0
        completed = swaps.filter(status='COMPLETE').count()
        return round((completed / total) * 100, 1)

class AgentTransactionsView(LoginRequiredMixin, AgentRequiredMixin, ListView):
    model = SwapRequest
    template_name = 'swap_app/agent_transactions.html'
    context_object_name = 'transactions'
    
    def get_queryset(self):
        return SwapRequest.objects.filter(agent__user=self.request.user).order_by('-created_at')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        transactions = context['transactions']
        
        # Pre-calculate counts for the template
        context.update({
            'total_transactions': transactions.count(),
            'completed_count': transactions.filter(status='COMPLETE').count(),
            'pending_count': transactions.filter(status='PENDING').count(),
            'active_count': transactions.filter(status__in=['ACCEPTED', 'PAID_BANK']).count(),
            'failed_count': transactions.filter(status__in=['REJECTED', 'CANCELLED']).count(),
        })
        return context

class AgentWalletView(LoginRequiredMixin, AgentRequiredMixin, TemplateView):
    template_name = 'swap_app/agent_wallet.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        agent = self.request.user.agent
        wallets = AgentWallet.objects.filter(agent=self.request.user)
        
        # Pre-calculate the counts to avoid template errors
        tnm_completed_count = agent.swap_requests.filter(to_service='TNM', status='COMPLETE').count()
        airtel_completed_count = agent.swap_requests.filter(to_service='AIRTEL', status='COMPLETE').count()
        completed_swaps_count = agent.swap_requests.filter(status='COMPLETE').count()
        total_swaps_count = agent.swap_requests.count()
        
        # Calculate success rate
        success_rate = 0
        if total_swaps_count > 0:
            success_rate = (completed_swaps_count / total_swaps_count) * 100
        
        # Calculate average commission
        average_commission = 0
        if completed_swaps_count > 0:
            completed_swaps = agent.swap_requests.filter(status='COMPLETE')
            total_commission = completed_swaps.aggregate(Sum('agent_fee'))['agent_fee__sum'] or 0
            average_commission = total_commission / completed_swaps_count
        
        context.update({
            'agent': agent,
            'wallets': wallets,
            'total_earnings': wallets.aggregate(Sum('total_earnings'))['total_earnings__sum'] or 0,
            'available_balance': wallets.aggregate(Sum('available_balance'))['available_balance__sum'] or 0,
            'tnm_completed_count': tnm_completed_count,
            'airtel_completed_count': airtel_completed_count,
            'completed_swaps_count': completed_swaps_count,
            'total_swaps_count': total_swaps_count,
            'success_rate': round(success_rate, 1),
            'average_commission': average_commission,
        })
        return context

# Location & Notifications
class UpdateLocationView(LoginRequiredMixin, View):
    def post(self, request):
        try:
            data = json.loads(request.body)
            lat = data.get('lat')
            lng = data.get('lng')
            address = data.get('address', '')
            
            if lat and lng:
                request.user.location_lat = lat
                request.user.location_lng = lng
                request.user.location_address = address
                request.user.save()
                
                return JsonResponse({
                    'success': True,
                    'message': 'Location updated successfully'
                })
            else:
                return JsonResponse({
                    'success': False,
                    'error': 'Invalid coordinates'
                })
                
        except json.JSONDecodeError:
            return JsonResponse({
                'success': False,
                'error': 'Invalid JSON data'
            })

class GetDistanceView(LoginRequiredMixin, View):
    def post(self, request):
        try:
            data = json.loads(request.body)
            agent_id = data.get('agent_id')
            
            agent = get_object_or_404(Agent, id=agent_id)
            
            if not request.user.has_location or not agent.user.has_location:
                return JsonResponse({
                    'success': False,
                    'error': 'Location data missing'
                })
            
            distance = self.calculate_distance(
                float(request.user.location_lat),
                float(request.user.location_lng),
                float(agent.user.location_lat),
                float(agent.user.location_lng)
            )
            
            return JsonResponse({
                'success': True,
                'distance_km': round(distance, 2),
                'agent_location': agent.user.location_address
            })
            
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            })
    
    def calculate_distance(self, lat1, lon1, lat2, lon2):
        R = 6371
        
        lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
        
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        
        a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
        c = 2 * atan2(sqrt(a), sqrt(1-a))
        
        return R * c

class ToggleOnlineStatusView(LoginRequiredMixin, View):
    def post(self, request):
        try:
            agent = request.user.agent
            agent.is_online = not agent.is_online
            agent.save()
            return JsonResponse({
                'success': True, 
                'is_online': agent.is_online
            })
        except Agent.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'User is not an agent'})

class NotificationListView(LoginRequiredMixin, ListView):
    model = Notification
    template_name = 'swap_app/notifications.html'
    context_object_name = 'notifications'
    
    def get_queryset(self):
        return Notification.objects.filter(user=self.request.user).order_by('-created_at')
    
    def post(self, request):
        Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
        return redirect('notifications')

# Webhook endpoints
@csrf_exempt
def webhook_bank(request):
    try:
        data = json.loads(request.body.decode('utf-8'))
        ref = data.get('reference')
        provider_tx_id = data.get('tx_id')
        amount = data.get('amount')
        
        swap = SwapRequest.objects.filter(reference=ref).first()
        if not swap:
            return JsonResponse({'ok': False, 'error': 'Swap not found'}, status=404)
        
        TransactionLog.objects.create(
            swap_request=swap,
            type='BANK_WEBHOOK',
            provider_tx_id=provider_tx_id,
            payload=data
        )
        
        if amount and float(amount) == float(swap.amount):
            swap.status = 'PAID_BANK'
            swap.save()
        
        return JsonResponse({'ok': True})
    
    except json.JSONDecodeError:
        return JsonResponse({'ok': False, 'error': 'Invalid JSON'}, status=400)

@csrf_exempt
def webhook_wallet(request):
    try:
        data = json.loads(request.body.decode('utf-8'))
        ref = data.get('reference')
        provider_tx_id = data.get('tx_id')
        
        swap = SwapRequest.objects.filter(reference=ref).first()
        if not swap:
            return JsonResponse({'ok': False, 'error': 'Swap not found'}, status=404)
        
        TransactionLog.objects.create(
            swap_request=swap,
            type='WALLET_WEBHOOK',
            provider_tx_id=provider_tx_id,
            payload=data
        )
        
        swap.status = 'COMPLETE'
        swap.save()
        
        return JsonResponse({'ok': True})
    
    except json.JSONDecodeError:
        return JsonResponse({'ok': False, 'error': 'Invalid JSON'}, status=400)

# Theme toggle
class ThemeToggleView(View):
    def get(self, request, *args, **kwargs):
        # Toggle dark mode
        if 'dark_mode' in request.session:
            request.session['dark_mode'] = not request.session['dark_mode']
        else:
            request.session['dark_mode'] = True
        
        # Ensure session is saved
        request.session.modified = True
        
        # Redirect to previous page or home
        return redirect(request.META.get('HTTP_REFERER', 'home'))