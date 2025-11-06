from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone
import uuid

class User(AbstractUser):
    ROLE_CHOICES = (
        ('client', 'Client'),
        ('agent', 'Agent'),
        ('admin', 'Admin'),
    )
    
    phone_number = models.CharField(max_length=15, unique=True)
    national_id = models.CharField(max_length=20, blank=True)
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default='client')
    is_verified = models.BooleanField(default=False)
    location_lat = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    location_lng = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    location_address = models.CharField(max_length=255, blank=True)
    
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

class Agent(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    bank_name = models.CharField(max_length=100, blank=True)
    bank_account = models.CharField(max_length=50, blank=True)
    mpamba_number = models.CharField(max_length=20, blank=True)
    airtel_number = models.CharField(max_length=20, blank=True)
    verified = models.BooleanField(default=False)
    float_mpamba = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    float_airtel = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    security_deposit = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    rating = models.FloatField(default=5.0)
    joined_at = models.DateTimeField(default=timezone.now)
    is_online = models.BooleanField(default=False)
    max_swap_amount = models.DecimalField(max_digits=14, decimal_places=2, default=50000)
    response_time = models.IntegerField(default=15)  # minutes
    
    def __str__(self):
        return f"Agent: {self.user.username}"
    
    @property
    def location_data(self):
        if self.user.has_location:
            return {
                'lat': float(self.user.location_lat),
                'lng': float(self.user.location_lng),
                'address': self.user.location_address,
                'username': self.user.username,
                'rating': self.rating,
                'float_mpamba': float(self.float_mpamba),
                'float_airtel': float(self.float_airtel),
            }
        return None

class Account(models.Model):
    ACCOUNT_TYPES = (
        ('bank', 'Bank Account'),
        ('mpamba', 'TNM Mpamba'),
        ('airtel_money', 'Airtel Money'),
    )
    
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    account_type = models.CharField(max_length=15, choices=ACCOUNT_TYPES)
    account_name = models.CharField(max_length=100)
    account_number = models.CharField(max_length=50)
    bank_name = models.CharField(max_length=100, blank=True)
    balance = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.user.username} - {self.account_type}"

class SwapRequest(models.Model):
    STATUS_CHOICES = (
        ('PENDING', 'Pending Agent Acceptance'),
        ('ACCEPTED', 'Accepted by Agent'),
        ('REJECTED', 'Rejected by Agent'),
        ('RESERVED', 'Reserved'),
        ('PAID_BANK', 'Paid to Agent Bank'),
        ('SENT_WALLET', 'Agent Sent Wallet'),
        ('COMPLETE', 'Complete'),
        ('DISPUTE', 'Dispute'),
        ('CANCELLED', 'Cancelled'),
    )
    
    WALLET_CHOICES = (
        ('TNM', 'TNM Mpamba'),
        ('AIRTEL', 'Airtel Money'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    client = models.ForeignKey(User, on_delete=models.CASCADE, related_name='swap_requests')
    agent = models.ForeignKey(Agent, on_delete=models.CASCADE, related_name='swap_requests')
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    from_service = models.CharField(max_length=15, choices=Account.ACCOUNT_TYPES)
    to_service = models.CharField(max_length=10, choices=WALLET_CHOICES)
    dest_number = models.CharField(max_length=20)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    reference = models.CharField(max_length=32, unique=True)
    platform_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    agent_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    bank_deposit_proof = models.FileField(upload_to='proofs/bank/', blank=True)
    agent_tx_id = models.CharField(max_length=128, blank=True)
    agent_response_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"Swap {self.reference} - {self.amount}"
    
    @property
    def net_amount(self):
        return self.amount - (self.platform_fee + self.agent_fee)

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

class TransactionLog(models.Model):
    swap_request = models.ForeignKey(SwapRequest, related_name='logs', on_delete=models.CASCADE)
    type = models.CharField(max_length=30)
    provider_tx_id = models.CharField(max_length=128, blank=True)
    payload = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"Log {self.type} for {self.swap_request.reference}"

class AgentWallet(models.Model):
    SERVICE_CHOICES = (
        ('bank', 'Bank'),
        ('mpamba', 'TNM Mpamba'),
        ('airtel_money', 'Airtel Money'),
    )
    
    agent = models.ForeignKey(User, on_delete=models.CASCADE)
    service_type = models.CharField(max_length=15, choices=SERVICE_CHOICES)
    available_balance = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    total_earnings = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    last_updated = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['agent', 'service_type']
    
    def __str__(self):
        return f"{self.agent.username} - {self.service_type}"