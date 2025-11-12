from datetime import timezone
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.db.models import Count, Sum
from .models import User, Agent, SwapRequest, ProofUpload, Dispute, Notification, Block, BlockchainEvent, KYCDocument

@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = ('username', 'email', 'phone_number', 'role', 'is_verified', 'date_joined')
    list_filter = ('role', 'is_verified', 'is_staff', 'date_joined')
    search_fields = ('username', 'email', 'phone_number')
    fieldsets = UserAdmin.fieldsets + (
        ('MoneySwap Info', {'fields': ('phone_number', 'national_id', 'role', 'is_verified', 'location_address', 'verification_level', 'daily_swap_limit', 'max_swap_amount')}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ('MoneySwap Info', {'fields': ('phone_number', 'national_id', 'role')}),
    )

@admin.register(Agent)
class AgentAdmin(admin.ModelAdmin):
    list_display = ('user', 'bank_name', 'verified', 'trust_score', 'trust_level', 'completed_swaps', 'is_online')
    list_filter = ('verified', 'trust_level', 'is_online')
    search_fields = ('user__username', 'bank_account', 'mpamba_number')
    readonly_fields = ('trust_score', 'completion_rate', 'average_response_time')
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user')

@admin.register(SwapRequest)
class SwapRequestAdmin(admin.ModelAdmin):
    list_display = ('reference', 'client', 'agent', 'amount', 'from_service', 'to_service', 'status', 'created_at')
    list_filter = ('status', 'from_service', 'to_service', 'created_at')
    readonly_fields = ('reference', 'created_at', 'updated_at')
    search_fields = ('reference', 'client__username', 'agent__user__username')
    actions = ['mark_as_complete', 'mark_as_dispute']
    
    def mark_as_complete(self, request, queryset):
        updated = queryset.update(status='COMPLETE')
        self.message_user(request, f'{updated} swaps marked as complete')
    mark_as_complete.short_description = "Mark selected swaps as complete"
    
    def mark_as_dispute(self, request, queryset):
        updated = queryset.update(status='DISPUTE')
        self.message_user(request, f'{updated} swaps marked as dispute')
    mark_as_dispute.short_description = "Mark selected swaps as dispute"

@admin.register(ProofUpload)
class ProofUploadAdmin(admin.ModelAdmin):
    list_display = ('swap_request', 'proof_type', 'status', 'confidence_score', 'created_at')
    list_filter = ('proof_type', 'status', 'created_at')
    readonly_fields = ('created_at',)
    actions = ['verify_proofs', 'reject_proofs']
    
    def verify_proofs(self, request, queryset):
        updated = queryset.update(status='verified')
        self.message_user(request, f'{updated} proofs verified')
    verify_proofs.short_description = "Verify selected proofs"
    
    def reject_proofs(self, request, queryset):
        updated = queryset.update(status='rejected')
        self.message_user(request, f'{updated} proofs rejected')
    reject_proofs.short_description = "Reject selected proofs"

@admin.register(Dispute)
class DisputeAdmin(admin.ModelAdmin):
    list_display = ('swap_request', 'severity', 'status', 'created_at')
    list_filter = ('severity', 'status', 'created_at')
    readonly_fields = ('created_at',)
    actions = ['resolve_disputes', 'escalate_disputes']
    
    def resolve_disputes(self, request, queryset):
        updated = queryset.update(status='resolved')
        self.message_user(request, f'{updated} disputes resolved')
    resolve_disputes.short_description = "Resolve selected disputes"
    
    def escalate_disputes(self, request, queryset):
        updated = queryset.update(status='escalated')
        self.message_user(request, f'{updated} disputes escalated')
    escalate_disputes.short_description = "Escalate selected disputes"

@admin.register(Block)
class BlockAdmin(admin.ModelAdmin):
    list_display = ('index', 'timestamp', 'block_hash', 'created_at')
    readonly_fields = ('index', 'timestamp', 'previous_hash', 'block_hash', 'nonce', 'node_signature', 'validator_signatures')
    list_filter = ('timestamp',)

@admin.register(BlockchainEvent)
class BlockchainEventAdmin(admin.ModelAdmin):
    list_display = ('event_type', 'entity_ref', 'timestamp', 'block')
    list_filter = ('event_type', 'timestamp')
    readonly_fields = ('event_id', 'timestamp', 'payload_hash', 'signature')
    search_fields = ('entity_ref',)

@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('user', 'type', 'is_read', 'created_at')
    list_filter = ('type', 'is_read', 'created_at')
    readonly_fields = ('created_at',)
    actions = ['mark_as_read', 'mark_as_unread']
    
    def mark_as_read(self, request, queryset):
        updated = queryset.update(is_read=True)
        self.message_user(request, f'{updated} notifications marked as read')
    mark_as_read.short_description = "Mark selected as read"
    
    def mark_as_unread(self, request, queryset):
        updated = queryset.update(is_read=False)
        self.message_user(request, f'{updated} notifications marked as unread')
    mark_as_unread.short_description = "Mark selected as unread"

@admin.register(KYCDocument)
class KYCDocumentAdmin(admin.ModelAdmin):
    list_display = ('user', 'document_type', 'status', 'submitted_at')
    list_filter = ('document_type', 'status', 'submitted_at')
    readonly_fields = ('submitted_at',)
    actions = ['approve_kyc', 'reject_kyc']
    
    def approve_kyc(self, request, queryset):
        for kyc in queryset:
            kyc.status = 'approved'
            kyc.reviewed_by = request.user
            kyc.reviewed_at = timezone.now()
            kyc.save()
            kyc.user.is_verified = True
            kyc.user.verification_level = 'full'
            kyc.user.save()
        self.message_user(request, f'{queryset.count()} KYC documents approved')
    approve_kyc.short_description = "Approve selected KYC"
    
    def reject_kyc(self, request, queryset):
        updated = queryset.update(status='rejected', reviewed_by=request.user, reviewed_at=timezone.now())
        self.message_user(request, f'{updated} KYC documents rejected')
    reject_kyc.short_description = "Reject selected KYC"

class DashboardAdmin(admin.AdminSite):
    site_header = "MoneySwap Administration"
    site_title = "MoneySwap Admin"
    index_title = "Dashboard"

    def index(self, request, extra_context=None):
        # Add custom statistics to the admin dashboard
        stats = {
            'total_users': User.objects.count(),
            'total_agents': Agent.objects.filter(verified=True).count(),
            'total_swaps': SwapRequest.objects.count(),
            'pending_verification': Agent.objects.filter(verified=False).count(),
            'pending_disputes': Dispute.objects.filter(status='open').count(),
            'total_volume': SwapRequest.objects.filter(status='COMPLETE').aggregate(Sum('amount'))['amount__sum'] or 0,
            'platform_earnings': SwapRequest.objects.filter(status='COMPLETE').aggregate(Sum('platform_fee'))['platform_fee__sum'] or 0,
        }
        
        extra_context = extra_context or {}
        extra_context['stats'] = stats
        return super().index(request, extra_context)