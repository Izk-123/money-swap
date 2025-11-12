from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse_lazy
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.messages.views import SuccessMessageMixin
from django.views.generic import TemplateView, CreateView, ListView, DetailView, UpdateView, View
from django.http import JsonResponse, HttpResponseForbidden
from django.utils.crypto import get_random_string
from django.db import transaction
from django.utils import timezone
from datetime import timedelta
import json
from decimal import Decimal, InvalidOperation

from money_swapv2 import settings

from .models import User, SwapRequest, Agent, ProofUpload, Dispute, Notification
from .forms import CustomUserCreationForm, SwapRequestForm, ProofUploadForm, DisputeForm
from .services.swap_service import SwapService
from .services.proof_parser import ProofParser
from .services.blockchain_service import BlockchainService
from .services.recommendation_service import RecommendationService
from swap_app import models

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
        # If the user is an agent, create an Agent profile
        if self.object.role == 'agent':
            Agent.objects.create(user=self.object)
        return response

# Dashboard Views
class DashboardView(LoginRequiredMixin, TemplateView):
    template_name = 'swap_app/dashboard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user

        if user.role == 'client':
            swaps = SwapRequest.objects.filter(client=user)
            context.update({
                'total_swaps': swaps.count(),
                'pending_swaps': swaps.filter(status='PENDING').count(),
                'active_swaps': swaps.filter(status__in=['ACCEPTED', 'AWAITING_CLIENT_PROOF', 'CLIENT_PROOF_UPLOADED', 'AWAITING_AGENT_PROOF']).count(),
                'completed_swaps': swaps.filter(status='COMPLETE').count(),
                'recent_swaps': swaps.order_by('-created_at')[:5]
            })
        elif user.role == 'agent':
            agent = getattr(user, 'agent', None)
            if agent:
                agent_swaps = agent.swap_requests.all()
                context.update({
                    'agent': agent,
                    'pending_requests': agent_swaps.filter(status='PENDING').count(),
                    'active_swaps': agent_swaps.filter(status__in=['ACCEPTED', 'AWAITING_CLIENT_PROOF', 'CLIENT_PROOF_UPLOADED', 'AWAITING_AGENT_PROOF']).count(),
                    'recent_swaps': agent_swaps.order_by('-created_at')[:5],
                    'success_rate': agent.completion_rate,
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
        # Get filter parameters
        amount = self.request.GET.get('amount')
        service = self.request.GET.get('service')
        
        # If specific swap parameters provided, use recommendation engine
        if amount and service:
            try:
                amount_decimal = Decimal(amount)
                recommended_agents = RecommendationService.find_recommended_agents(
                    client=self.request.user,
                    amount=amount_decimal,
                    to_service=service
                )
                # Extract agents from recommendation data
                return [item['agent'] for item in recommended_agents]
            except (ValueError, InvalidOperation):
                pass
        
        # Default: show all verified online agents
        return Agent.objects.filter(
            verified=True,
            is_online=True
        ).select_related('user').order_by('-trust_score', '-completed_swaps')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        
        # Get recommendation data if specific swap parameters
        amount = self.request.GET.get('amount')
        service = self.request.GET.get('service')
        
        if amount and service:
            try:
                amount_decimal = Decimal(amount)
                context['recommended_agents_data'] = RecommendationService.find_recommended_agents(
                    client=user,
                    amount=amount_decimal,
                    to_service=service
                )
                context['swap_amount'] = amount
                context['swap_service'] = service
            except (ValueError, InvalidOperation):
                pass
        
        # Location data for maps
        context['client_location'] = user.location_address
        context['client_has_location'] = user.has_location
        
        if user.has_location:
            context['client_lat'] = float(user.location_lat)
            context['client_lng'] = float(user.location_lng)
        
        # Prepare agents data for maps
        agents_data = []
        for agent in context['agents']:
            if agent.user.has_location:
                agents_data.append({
                    'id': agent.id,
                    'username': agent.user.username,
                    'lat': float(agent.user.location_lat),
                    'lng': float(agent.user.location_lng),
                    'address': agent.user.location_address,
                    'rating': agent.trust_score,
                    'trust_level': agent.trust_level,
                    'is_online': agent.is_online,
                    'completed_swaps': agent.completed_swaps,
                })
        
        context['agents_data_json'] = json.dumps(agents_data)
        context['google_maps_api_key'] = settings.GOOGLE_MAPS_API_KEY
        
        return context

class CreateSwapView(LoginRequiredMixin, SuccessMessageMixin, CreateView):
    model = SwapRequest
    form_class = SwapRequestForm
    template_name = 'swap_app/create_swap.html'
    success_message = "Swap request created! Please upload your payment proof."

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def form_valid(self, form):
        try:
            with transaction.atomic():
                swap = form.save(commit=False)
                swap.client = self.request.user
                swap.reference = f"SWAP{get_random_string(8).upper()}"

                # Calculate fees (for reporting only - no real collection)
                total_fee = max(swap.amount * Decimal('0.006'), Decimal('50'))
                swap.platform_fee = (total_fee * Decimal('0.25')).quantize(Decimal('0.01'))
                swap.agent_fee = (total_fee * Decimal('0.75')).quantize(Decimal('0.01'))

                # Validate agent selection
                if not swap.agent.can_accept_swap:
                    form.add_error('agent', 'Selected agent has reached daily swap limit')
                    return self.form_invalid(form)

                swap.save()

                # Notify agent
                Notification.objects.create(
                    user=swap.agent.user,
                    swap_request=swap,
                    type='swap_request',
                    message=f"New swap request: MWK {swap.amount} from {swap.client.username}"
                )

                # Record on blockchain
                blockchain_service = BlockchainService()
                blockchain_service.record_swap_created(swap, self.request.user)

                self.object = swap

            return super().form_valid(form)

        except Exception as e:
            messages.error(self.request, f'Error creating swap: {str(e)}')
            return self.form_invalid(form)

    def get_success_url(self):
        return reverse_lazy('upload_client_proof', kwargs={'pk': self.object.pk})

class UploadClientProofView(LoginRequiredMixin, DetailView):
    model = SwapRequest
    template_name = 'swap_app/upload_proof.html'
    context_object_name = 'swap'

    def get_queryset(self):
        return SwapRequest.objects.filter(client=self.request.user, status='ACCEPTED')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['proof_form'] = ProofUploadForm()
        context['proof_type'] = 'client'
        return context

    def post(self, request, *args, **kwargs):
        swap = self.get_object()
        form = ProofUploadForm(request.POST, request.FILES)

        if form.is_valid():
            with transaction.atomic():
                proof = form.save(commit=False)
                proof.swap_request = swap
                proof.uploaded_by = request.user

                # Auto-parse proof content
                parsed_data = {}
                if proof.sms_text:
                    parsed_data = ProofParser.parse_sms(proof.sms_text)
                elif proof.image_file:
                    parsed_data = ProofParser.parse_image(proof.image_file)

                if parsed_data:
                    proof.extracted_amount = parsed_data.get('amount')
                    proof.extracted_reference = parsed_data.get('reference')
                    proof.extracted_txid = parsed_data.get('txid')
                    proof.extracted_account = parsed_data.get('account')
                    proof.confidence_score = parsed_data.get('confidence', 0.0)

                proof.save()

                # Update swap status
                swap.status = 'CLIENT_PROOF_UPLOADED'
                swap.client_proof_uploaded_at = timezone.now()
                swap.save()

                # Notify agent
                Notification.objects.create(
                    user=swap.agent.user,
                    swap_request=swap,
                    type='payment_received',
                    message=f"Client uploaded payment proof for swap {swap.reference}"
                )

                # Record on blockchain
                blockchain_service = BlockchainService()
                blockchain_service.record_swap_paid_bank(swap, request.user)

                messages.success(request, "Payment proof uploaded! Agent has been notified to send wallet funds.")
                return redirect('swap_detail', pk=swap.pk)

        messages.error(request, "Error uploading proof. Please check the form.")
        return self.render_to_response(self.get_context_data(proof_form=form))

class UploadAgentProofView(LoginRequiredMixin, DetailView):
    model = SwapRequest
    template_name = 'swap_app/upload_proof.html'
    context_object_name = 'swap'

    def get_queryset(self):
        return SwapRequest.objects.filter(agent__user=self.request.user, status='CLIENT_PROOF_UPLOADED')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['proof_form'] = ProofUploadForm()
        context['proof_type'] = 'agent'
        return context

    def post(self, request, *args, **kwargs):
        swap = self.get_object()
        form = ProofUploadForm(request.POST, request.FILES)

        if form.is_valid():
            with transaction.atomic():
                proof = form.save(commit=False)
                proof.swap_request = swap
                proof.uploaded_by = request.user

                # Auto-parse proof content
                parsed_data = {}
                if proof.sms_text:
                    parsed_data = ProofParser.parse_sms(proof.sms_text)
                elif proof.image_file:
                    parsed_data = ProofParser.parse_image(proof.image_file)

                if parsed_data:
                    proof.extracted_amount = parsed_data.get('amount')
                    proof.extracted_txid = parsed_data.get('txid')
                    proof.confidence_score = parsed_data.get('confidence', 0.0)

                    # Auto-verify if confidence is high
                    if proof.confidence_score > 0.8:
                        proof.status = 'verified'

                proof.save()

                # Update swap status
                swap.status = 'AGENT_PROOF_UPLOADED'
                swap.agent_proof_uploaded_at = timezone.now()
                swap.save()

                # Record on blockchain
                blockchain_service = BlockchainService()
                blockchain_service.record_swap_sent_wallet(swap, request.user)

                # Auto-complete if both proofs are verified
                if swap.has_client_proof and proof.status == 'verified':
                    SwapService.complete_swap(swap)
                    messages.success(request, "Swap completed automatically!")
                else:
                    messages.success(request, "Send proof uploaded! Waiting for verification.")

                return redirect('swap_detail', pk=swap.pk)

        messages.error(request, "Error uploading proof.")
        return self.render_to_response(self.get_context_data(proof_form=form))

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

class AgentResponseView(LoginRequiredMixin, View):
    def post(self, request, pk):
        swap = get_object_or_404(SwapRequest, pk=pk, agent__user=request.user)
        action = request.POST.get('action')

        with transaction.atomic():
            if action == 'accept':
                if not swap.agent.can_accept_swap:
                    return JsonResponse({'success': False, 'error': 'Daily swap limit reached'})

                swap.status = 'ACCEPTED'
                swap.agent_response_at = timezone.now()
                message = f"Agent {request.user.username} accepted your swap request"
                notification_type = 'swap_accepted'

                # Update agent response metrics
                response_time = (swap.agent_response_at - swap.created_at).total_seconds()
                swap.agent.update_response_time(response_time)

                # Record on blockchain
                blockchain_service = BlockchainService()
                blockchain_service.record_swap_reserved(swap, request.user)
            else:
                swap.status = 'REJECTED'
                message = f"Agent {request.user.username} rejected your swap request"
                notification_type = 'swap_rejected'

            swap.save()

            Notification.objects.create(
                user=swap.client,
                swap_request=swap,
                type=notification_type,
                message=message
            )

            return JsonResponse({'success': True})

        return JsonResponse({'success': False, 'error': 'Invalid action'})

# Theme Toggle View
class ThemeToggleView(View):
    def get(self, request, *args, **kwargs):
        if 'dark_mode' in request.session:
            request.session['dark_mode'] = not request.session['dark_mode']
        else:
            request.session['dark_mode'] = True

        request.session.modified = True
        return redirect(request.META.get('HTTP_REFERER', 'home'))

# Agent Dashboard Views
class AgentDashboardView(LoginRequiredMixin, TemplateView):
    template_name = 'swap_app/agent_dashboard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        agent = self.request.user.agent
        swaps = agent.swap_requests.all()

        today = timezone.now().date()
        week_ago = today - timedelta(days=7)
        month_ago = today - timedelta(days=30)

        weekly_earnings = swaps.filter(
            status='COMPLETE',
            created_at__gte=week_ago
        ).aggregate(models.Sum('agent_fee'))['agent_fee__sum'] or 0

        monthly_earnings = swaps.filter(
            status='COMPLETE', 
            created_at__gte=month_ago
        ).aggregate(models.Sum('agent_fee'))['agent_fee__sum'] or 0

        context.update({
            'agent': agent,
            'swaps': swaps.order_by('-created_at'),
            'weekly_earnings': weekly_earnings,
            'monthly_earnings': monthly_earnings,
            'pending_swaps': swaps.filter(status='PENDING').count(),
            'awaiting_send': swaps.filter(status='CLIENT_PROOF_UPLOADED').count(),
            'success_rate': agent.completion_rate,
        })
        return context

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

# API Views
class AgentRecommendationAPIView(LoginRequiredMixin, View):
    """API endpoint for real-time agent recommendations"""
    
    def get(self, request):
        amount = request.GET.get('amount')
        service = request.GET.get('service')
        
        if not amount or not service:
            return JsonResponse({'error': 'Amount and service required'}, status=400)
        
        try:
            amount_decimal = Decimal(amount)
            recommended_agents = RecommendationService.find_recommended_agents(
                client=request.user,
                amount=amount_decimal,
                to_service=service,
                max_results=3
            )
            
            # Serialize data for API response
            agents_data = []
            for agent_data in recommended_agents:
                agents_data.append({
                    'id': agent_data['agent'].id,
                    'username': agent_data['agent'].user.username,
                    'trust_score': agent_data['trust_score'],
                    'trust_level': agent_data['trust_level'],
                    'distance_km': agent_data['distance_km'],
                    'estimated_time': agent_data['estimated_time'],
                    'completion_rate': agent_data['completion_rate'],
                    'response_time': agent_data['average_response_time'],
                })
            
            return JsonResponse({
                'agents': agents_data,
                'swap_amount': amount,
                'swap_service': service
            })
            
        except (ValueError, InvalidOperation) as e:
            return JsonResponse({'error': 'Invalid amount'}, status=400)