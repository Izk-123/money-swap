from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import User, Account, SwapRequest, Agent

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

class AccountForm(forms.ModelForm):
    class Meta:
        model = Account
        fields = ('account_type', 'account_name', 'account_number', 'bank_name', 'balance')
        widgets = {
            'bank_name': forms.TextInput(attrs={'placeholder': 'Only for bank accounts'}),
        }

class SwapRequestForm(forms.ModelForm):
    agent = forms.ModelChoiceField(
        queryset=Agent.objects.none(),
        empty_label="Select an agent",
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    class Meta:
        model = SwapRequest
        fields = ('amount', 'from_service', 'to_service', 'dest_number', 'agent')
        widgets = {
            'amount': forms.NumberInput(attrs={
                'min': '10', 
                'step': '0.01',
                'class': 'form-control',
                'placeholder': 'Enter amount in MWK'
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
            self.fields['agent'].queryset = Agent.objects.filter(
                verified=True,
                is_online=True
            ).select_related('user')

class AgentResponseForm(forms.Form):
    action = forms.ChoiceField(
        choices=(('accept', 'Accept'), ('reject', 'Reject')),
        widget=forms.RadioSelect
    )
    reason = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'rows': 3,
            'placeholder': 'Optional reason for rejection...'
        })
    )

class ProofUploadForm(forms.ModelForm):
    class Meta:
        model = SwapRequest
        fields = ('bank_deposit_proof',)
        widgets = {
            'bank_deposit_proof': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': 'image/*,.pdf'
            })
        }

class LocationForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['location_address']
        widgets = {
            'location_address': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter your address...',
                'id': 'location-search'
            })
        }