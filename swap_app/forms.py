from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.core.exceptions import ValidationError
from decimal import Decimal
from .models import User, SwapRequest, ProofUpload, Dispute

class CustomUserCreationForm(UserCreationForm):
    phone_number = forms.CharField(max_length=15, required=True)
    national_id = forms.CharField(max_length=20, required=False)
    role = forms.ChoiceField(choices=User.ROLE_CHOICES)
    location_address = forms.CharField(max_length=255, required=False, widget=forms.TextInput(attrs={
        'placeholder': 'Enter your location (optional)'
    }))
    
    class Meta:
        model = User
        fields = ('username', 'email', 'phone_number', 'national_id', 'role', 'location_address', 'password1', 'password2')
    
    def clean_phone_number(self):
        phone_number = self.cleaned_data['phone_number']
        if not phone_number.startswith(('088', '099', '098')):
            raise ValidationError("Please enter a valid Malawi mobile number (starts with 088, 099, or 098)")
        return phone_number

class SwapRequestForm(forms.ModelForm):
    agent = forms.ModelChoiceField(
        queryset=User.objects.none(),
        empty_label="Select an agent",
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    class Meta:
        model = SwapRequest
        fields = ('amount', 'from_service', 'to_service', 'dest_number', 'agent')
        widgets = {
            'amount': forms.NumberInput(attrs={
                'min': '50', 
                'step': '0.01',
                'class': 'form-control',
                'placeholder': 'Enter amount in MWK (min: MK 50)'
            }),
            'dest_number': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '088... or 099...'
            }),
            'from_service': forms.Select(attrs={'class': 'form-select'}),
            'to_service': forms.Select(attrs={'class': 'form-select'}),
        }
    
    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if user:
            # Only show verified, online agents with capacity
            from .models import Agent
            self.fields['agent'].queryset = User.objects.filter(
                agent__verified=True,
                agent__is_online=True
            ).select_related('agent')
    
    def clean_amount(self):
        amount = self.cleaned_data['amount']
        user = getattr(self, 'user', None)
        
        if user and hasattr(user, 'max_swap_amount'):
            if amount > user.max_swap_amount:
                raise ValidationError(
                    f"Amount exceeds your maximum swap limit of MK {user.max_swap_amount}"
                )
            
            # Check daily limit
            todays_volume = user.todays_swap_volume
            if todays_volume + amount > user.daily_swap_limit:
                raise ValidationError(
                    f"This swap would exceed your daily limit of MK {user.daily_swap_limit}. "
                    f"Today's volume: MK {todays_volume}"
                )
        
        if amount < 50:
            raise ValidationError("Minimum swap amount is MK 50")
            
        return amount
    
    def clean_dest_number(self):
        dest_number = self.cleaned_data['dest_number']
        to_service = self.cleaned_data.get('to_service')
        
        if to_service == 'TNM' and not dest_number.startswith('088'):
            raise ValidationError("TNM Mpamba numbers must start with 088")
        elif to_service == 'AIRTEL' and not dest_number.startswith(('099', '098')):
            raise ValidationError("Airtel Money numbers must start with 099 or 098")
            
        return dest_number

class ProofUploadForm(forms.ModelForm):
    PROOF_TYPE_CHOICES = (
        ('bank_sms', 'Bank SMS'),
        ('bank_app', 'Bank App Screenshot'),
        ('bank_slip', 'Bank Deposit Slip'),
        ('wallet_sms', 'Wallet SMS'),
        ('wallet_app', 'Wallet App Screenshot'),
    )
    
    proof_type = forms.ChoiceField(choices=PROOF_TYPE_CHOICES, widget=forms.RadioSelect)
    image_file = forms.ImageField(required=False, widget=forms.FileInput(attrs={
        'accept': 'image/*,.pdf',
        'class': 'form-control'
    }))
    sms_text = forms.CharField(required=False, widget=forms.Textarea(attrs={
        'rows': 4,
        'placeholder': 'Paste SMS content here...',
        'class': 'form-control'
    }))
    
    class Meta:
        model = ProofUpload
        fields = ('proof_type', 'image_file', 'sms_text')
    
    def clean(self):
        cleaned_data = super().clean()
        proof_type = cleaned_data.get('proof_type')
        image_file = cleaned_data.get('image_file')
        sms_text = cleaned_data.get('sms_text')
        
        if proof_type in ['bank_sms', 'wallet_sms'] and not sms_text:
            raise ValidationError("Please paste the SMS content for SMS proof types")
        
        if proof_type in ['bank_app', 'wallet_app', 'bank_slip'] and not image_file:
            raise ValidationError("Please upload an image file for this proof type")
        
        return cleaned_data

class DisputeForm(forms.ModelForm):
    class Meta:
        model = Dispute
        fields = ('reason', 'severity')
        widgets = {
            'reason': forms.Textarea(attrs={
                'rows': 4,
                'placeholder': 'Describe the issue in detail...',
                'class': 'form-control'
            }),
            'severity': forms.Select(attrs={'class': 'form-select'}),
        }
    
    def clean_reason(self):
        reason = self.cleaned_data['reason']
        if len(reason.strip()) < 10:
            raise ValidationError("Please provide a detailed description of the issue (at least 10 characters)")
        return reason