from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone
import uuid
import os
import math
from decimal import Decimal

def proof_upload_path(instance, filename):
    """Generate upload path for proof files"""
    return f'proofs/{instance._meta.model_name}/{instance.id}/{filename}'

class User(AbstractUser):
    ROLE_CHOICES = (
        ('client', 'Client'),
        ('agent', 'Agent'),
        ('admin', 'Admin'),
    )
    
    VERIFICATION_LEVELS = (
        ('unverified', 'Unverified'),
        ('basic', 'Basic Verified'),
        ('full', 'Fully Verified'),
    )
    
    phone_number = models.CharField(max_length=15, unique=True)
    national_id = models.CharField(max_length=20, blank=True)
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default='client')
    verification_level = models.CharField(max_length=15, choices=VERIFICATION_LEVELS, default='unverified')
    is_verified = models.BooleanField(default=False)
    location_lat = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    location_lng = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    location_address = models.CharField(max_length=255, blank=True)
    daily_swap_limit = models.DecimalField(max_digits=14, decimal_places=2, default=20000)
    max_swap_amount = models.DecimalField(max_digits=14, decimal_places=2, default=5000)
    
    # Fix reverse accessor clashes
    groups = models.ManyToManyField(
        'auth.Group',
        verbose_name='groups',
        blank=True,
        help_text='The groups this user belongs to.',
        related_name='swap_user_set',
        related_query_name='user',
    )
    user_permissions = models.ManyToManyField(
        'auth.Permission',
        verbose_name='user permissions',
        blank=True,
        help_text='Specific permissions for this user.',
        related_name='swap_user_set',
        related_query_name='user',
    )
    
    def __str__(self):
        return f"{self.username} ({self.role})"
    
    @property
    def has_location(self):
        return bool(self.location_lat and self.location_lng)
    
    @property
    def todays_swap_volume(self):
        """Calculate today's total swap volume"""
        today = timezone.now().date()
        return self.swap_requests.filter(
            created_at__date=today
        ).aggregate(models.Sum('amount'))['amount__sum'] or 0

class Agent(models.Model):
    TRUST_LEVELS = (
        ('new', 'New Agent'),
        ('verified', 'Verified Agent'),
        ('trusted', 'Trusted Agent'),
    )
    
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    trust_level = models.CharField(max_length=10, choices=TRUST_LEVELS, default='new')
    bank_name = models.CharField(max_length=100, blank=True)
    bank_account = models.CharField(max_length=50, blank=True)
    mpamba_number = models.CharField(max_length=20, blank=True)
    airtel_number = models.CharField(max_length=20, blank=True)
    verified = models.BooleanField(default=False)
    
    # Capacity management (instead of float tracking)
    max_daily_swaps = models.IntegerField(default=10)
    current_daily_swaps = models.IntegerField(default=0)
    
    security_deposit = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    rating = models.FloatField(default=5.0)
    completed_swaps = models.IntegerField(default=0)
    joined_at = models.DateTimeField(default=timezone.now)
    is_online = models.BooleanField(default=False)
    max_swap_amount = models.DecimalField(max_digits=14, decimal_places=2, default=50000)
    response_time = models.IntegerField(default=15)
    
    # Trust scoring metrics
    total_response_time = models.FloatField(default=0)
    response_count = models.IntegerField(default=0)
    dispute_count = models.IntegerField(default=0)
    total_rating = models.FloatField(default=0)
    rating_count = models.IntegerField(default=0)
    
    def __str__(self):
        return f"Agent: {self.user.username}"
    
    @property
    def average_response_time(self):
        """Calculate average response time in minutes"""
        if self.response_count == 0:
            return self.response_time
        return (self.total_response_time / self.response_count) / 60
    
    @property
    def completion_rate(self):
        """Calculate completion rate percentage"""
        total_swaps = self.swap_requests.count()
        if total_swaps == 0:
            return 100.0
        return (self.completed_swaps / total_swaps) * 100
    
    @property
    def average_rating(self):
        """Calculate average rating"""
        if self.rating_count == 0:
            return self.rating
        return self.total_rating / self.rating_count
    
    @property
    def experience_score(self):
        """Calculate experience based on completed swaps"""
        if self.completed_swaps == 0:
            return 0
        return min(100, (math.log(self.completed_swaps + 1) / math.log(51)) * 100)
    
    @property
    def trust_score(self):
        """Calculate overall trust score (0-100%)"""
        weights = {
            'response_time': 0.2,
            'completion_rate': 0.3,
            'rating': 0.3,
            'experience': 0.2,
        }
        
        # Response time score (faster = better)
        response_score = max(0, 100 - (self.average_response_time * 2))
        response_score = min(100, response_score)
        
        # Completion rate score
        completion_score = self.completion_rate
        
        # Rating score
        rating_score = (self.average_rating / 5) * 100
        
        # Experience score
        experience_score = self.experience_score
        
        # Calculate weighted trust score
        trust_score = (
            response_score * weights['response_time'] +
            completion_score * weights['completion_rate'] +
            rating_score * weights['rating'] +
            experience_score * weights['experience']
        )
        
        # Penalty for disputes
        dispute_penalty = min(20, self.dispute_count * 5)
        trust_score = max(0, trust_score - dispute_penalty)
        
        return round(trust_score, 1)
    
    @property
    def trust_level(self):
        """Get human-readable trust level"""
        score = self.trust_score
        if score >= 90:
            return "Excellent"
        elif score >= 80:
            return "Very Good"
        elif score >= 70:
            return "Good"
        elif score >= 60:
            return "Fair"
        else:
            return "Needs Improvement"
    
    @property
    def can_accept_swap(self):
        """Check if agent can accept new swaps based on daily limit"""
        today = timezone.now().date()
        today_swaps = self.swap_requests.filter(
            created_at__date=today,
            status__in=['ACCEPTED', 'CLIENT_PROOF_UPLOADED', 'AGENT_PROOF_UPLOADED']
        ).count()
        return today_swaps < self.max_daily_swaps
    
    def get_payment_details(self, service_type):
        """Get agent's payment details for direct client transfer"""
        if service_type in ['national_bank', 'standard_bank', 'fdh_bank', 'nedbank']:
            return {
                'type': 'bank',
                'bank_name': self.bank_name,
                'account_number': self.bank_account,
                'account_name': self.user.get_full_name() or self.user.username
            }
        elif service_type == 'TNM':
            return {
                'type': 'mobile_money',
                'provider': 'TNM Mpamba',
                'number': self.mpamba_number
            }
        elif service_type == 'AIRTEL':
            return {
                'type': 'mobile_money', 
                'provider': 'Airtel Money',
                'number': self.airtel_number
            }
        return None
    
    def update_response_time(self, response_time_seconds):
        """Update average response time"""
        self.total_response_time += response_time_seconds
        self.response_count += 1
        self.save()
    
    def update_rating(self, new_rating):
        """Update average rating"""
        self.total_rating += new_rating
        self.rating_count += 1
        self.save()
    
    def add_dispute(self):
        """Increment dispute count"""
        self.dispute_count += 1
        self.save()

class KYCDocument(models.Model):
    DOCUMENT_TYPES = (
        ('national_id', 'National ID'),
        ('passport', 'Passport'),
        ('drivers_license', "Driver's License"),
    )
    
    STATUS_CHOICES = (
        ('pending', 'Pending Review'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    )
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='kyc_documents')
    document_type = models.CharField(max_length=20, choices=DOCUMENT_TYPES)
    document_front = models.ImageField(upload_to='kyc/documents/')
    document_back = models.ImageField(upload_to='kyc/documents/', blank=True)
    selfie_with_document = models.ImageField(upload_to='kyc/selfies/')
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    submitted_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='reviewed_kyc')
    rejection_reason = models.TextField(blank=True)
    
    def __str__(self):
        return f"{self.user.username} - {self.get_document_type_display()}"

class SwapRequest(models.Model):
    STATUS_CHOICES = (
        ('PENDING', 'Pending Agent Acceptance'),
        ('ACCEPTED', 'Accepted by Agent'),
        ('AWAITING_CLIENT_PROOF', 'Awaiting Client Payment Proof'),
        ('CLIENT_PROOF_UPLOADED', 'Client Proof Uploaded'),
        ('AWAITING_AGENT_PROOF', 'Awaiting Agent Send Proof'),
        ('AGENT_PROOF_UPLOADED', 'Agent Proof Uploaded'),
        ('COMPLETE', 'Complete'),
        ('DISPUTE', 'Dispute'),
        ('CANCELLED', 'Cancelled'),
        ('EXPIRED', 'Expired'),
    )
    
    WALLET_CHOICES = (
        ('TNM', 'TNM Mpamba'),
        ('AIRTEL', 'Airtel Money'),
    )
    
    BANK_CHOICES = (
        ('national_bank', 'National Bank'),
        ('standard_bank', 'Standard Bank'),
        ('fdh_bank', 'FDH Bank'),
        ('nedbank', 'Nedbank'),
        ('others', 'Other Banks'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    client = models.ForeignKey(User, on_delete=models.CASCADE, related_name='swap_requests')
    agent = models.ForeignKey(Agent, on_delete=models.CASCADE, related_name='swap_requests')
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    from_service = models.CharField(max_length=15, choices=BANK_CHOICES)
    to_service = models.CharField(max_length=10, choices=WALLET_CHOICES)
    dest_number = models.CharField(max_length=20)
    status = models.CharField(max_length=25, choices=STATUS_CHOICES, default='PENDING')
    reference = models.CharField(max_length=32, unique=True)
    
    # Fees (for reporting and invoicing only - no real-time collection)
    platform_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    agent_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    # Timing fields
    agent_response_at = models.DateTimeField(null=True, blank=True)
    client_proof_uploaded_at = models.DateTimeField(null=True, blank=True)
    agent_proof_uploaded_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Swap {self.reference} - {self.amount}"
    
    @property
    def net_amount(self):
        return self.amount - (self.platform_fee + self.agent_fee)
    
    @property
    def has_client_proof(self):
        return self.proofs.filter(
            uploaded_by=self.client, 
            status='verified'
        ).exists()
    
    @property
    def has_agent_proof(self):
        return self.proofs.filter(
            uploaded_by=self.agent.user, 
            status='verified'
        ).exists()
    
    @property
    def is_expired(self):
        if self.status == 'PENDING':
            return timezone.now() > self.created_at + timezone.timedelta(minutes=30)
        elif self.status == 'ACCEPTED':
            return timezone.now() > self.agent_response_at + timezone.timedelta(hours=2)
        return False

class ProofUpload(models.Model):
    PROOF_TYPES = (
        ('bank_sms', 'Bank SMS'),
        ('bank_app', 'Bank App Screenshot'),
        ('bank_slip', 'Bank Deposit Slip'),
        ('wallet_sms', 'Wallet SMS'),
        ('wallet_app', 'Wallet App Screenshot'),
        ('other', 'Other'),
    )
    
    STATUS_CHOICES = (
        ('pending', 'Pending Review'),
        ('verified', 'Verified'),
        ('rejected', 'Rejected'),
        ('needs_review', 'Needs Admin Review'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    swap_request = models.ForeignKey(SwapRequest, on_delete=models.CASCADE, related_name='proofs')
    uploaded_by = models.ForeignKey(User, on_delete=models.CASCADE)
    proof_type = models.CharField(max_length=15, choices=PROOF_TYPES)
    image_file = models.ImageField(upload_to=proof_upload_path, blank=True, null=True)
    sms_text = models.TextField(blank=True)
    extracted_amount = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    extracted_reference = models.CharField(max_length=100, blank=True)
    extracted_txid = models.CharField(max_length=100, blank=True)
    extracted_account = models.CharField(max_length=100, blank=True)
    extracted_date = models.DateTimeField(null=True, blank=True)
    confidence_score = models.FloatField(default=0.0)
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='pending')
    admin_notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Proof for {self.swap_request.reference}"

class Dispute(models.Model):
    SEVERITY_CHOICES = (
        ('low', 'Low - Missing Proof'),
        ('medium', 'Medium - Amount Mismatch'),
        ('high', 'High - Fraud Suspected'),
    )
    
    STATUS_CHOICES = (
        ('open', 'Open'),
        ('investigating', 'Under Investigation'),
        ('resolved', 'Resolved'),
        ('escalated', 'Escalated to Management'),
    )
    
    swap_request = models.OneToOneField(SwapRequest, on_delete=models.CASCADE)
    opened_by = models.ForeignKey(User, on_delete=models.CASCADE)
    reason = models.TextField()
    severity = models.CharField(max_length=10, choices=SEVERITY_CHOICES, default='low')
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='open')
    admin_notes = models.TextField(blank=True)
    resolution = models.TextField(blank=True)
    resolved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='resolved_disputes')
    resolved_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Dispute for {self.swap_request.reference}"

class Block(models.Model):
    """Blockchain block model"""
    index = models.BigIntegerField(unique=True)
    timestamp = models.DateTimeField()
    previous_hash = models.CharField(max_length=64)
    block_hash = models.CharField(max_length=64, unique=True)
    nonce = models.BigIntegerField(default=0)
    node_signature = models.TextField()
    validator_signatures = models.JSONField(default=list)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"Block #{self.index}"

class BlockchainEvent(models.Model):
    """Events stored on blockchain"""
    EVENT_TYPES = (
        ('KYC_SUBMITTED', 'KYC Submitted'),
        ('KYC_APPROVED', 'KYC Approved'),
        ('KYC_REJECTED', 'KYC Rejected'),
        ('SWAP_CREATED', 'Swap Created'),
        ('SWAP_RESERVED', 'Swap Reserved'),
        ('SWAP_PAID_BANK', 'Swap Paid Bank'),
        ('SWAP_SENT_WALLET', 'Swap Sent Wallet'),
        ('SWAP_COMPLETED', 'Swap Completed'),
        ('SWAP_CANCELLED', 'Swap Cancelled'),
        ('DISPUTE_OPENED', 'Dispute Opened'),
        ('DISPUTE_RESOLVED', 'Dispute Resolved'),
        ('AGENT_SUSPENDED', 'Agent Suspended'),
    )
    
    block = models.ForeignKey(Block, on_delete=models.CASCADE, related_name='events')
    event_id = models.CharField(max_length=64, unique=True)
    event_type = models.CharField(max_length=50, choices=EVENT_TYPES)
    timestamp = models.DateTimeField()
    entity_ref = models.CharField(max_length=100)
    payload_hash = models.CharField(max_length=64)
    actor = models.CharField(max_length=100)
    signature = models.TextField(blank=True)
    merkle_proof = models.JSONField(default=list)
    
    class Meta:
        ordering = ['-timestamp']
    
    def __str__(self):
        return f"{self.event_type} - {self.entity_ref}"

class Notification(models.Model):
    TYPE_CHOICES = (
        ('swap_request', 'Swap Request'),
        ('swap_accepted', 'Swap Accepted'),
        ('swap_rejected', 'Swap Rejected'),
        ('payment_received', 'Payment Received'),
        ('payment_sent', 'Payment Sent'),
        ('system', 'System'),
    )
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    swap_request = models.ForeignKey(SwapRequest, on_delete=models.CASCADE, null=True, blank=True)
    type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"Notification for {self.user.username} - {self.type}"