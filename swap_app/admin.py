from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User, Agent, Account, SwapRequest, Notification, TransactionLog, AgentWallet

@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = ('username', 'email', 'phone_number', 'role', 'is_verified', 'date_joined')
    list_filter = ('role', 'is_verified', 'is_staff')
    fieldsets = UserAdmin.fieldsets + (
        ('MoneySwap Info', {'fields': ('phone_number', 'national_id', 'role', 'is_verified', 'location_address')}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ('MoneySwap Info', {'fields': ('phone_number', 'national_id', 'role')}),
    )

@admin.register(Agent)
class AgentAdmin(admin.ModelAdmin):
    list_display = ('user', 'bank_name', 'mpamba_number', 'verified', 'rating', 'float_mpamba', 'float_airtel')
    list_filter = ('verified',)
    search_fields = ('user__username', 'bank_account', 'mpamba_number')

@admin.register(Account)
class AccountAdmin(admin.ModelAdmin):
    list_display = ('user', 'account_type', 'account_name', 'account_number', 'balance', 'is_active')
    list_filter = ('account_type', 'is_active')

@admin.register(SwapRequest)
class SwapRequestAdmin(admin.ModelAdmin):
    list_display = ('reference', 'client', 'agent', 'amount', 'to_service', 'status', 'created_at')
    list_filter = ('status', 'to_service', 'created_at')
    readonly_fields = ('reference', 'created_at', 'updated_at')
    search_fields = ('reference', 'client__username', 'agent__user__username')

@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('user', 'type', 'message', 'is_read', 'created_at')
    list_filter = ('type', 'is_read', 'created_at')
    readonly_fields = ('created_at',)

@admin.register(TransactionLog)
class TransactionLogAdmin(admin.ModelAdmin):
    list_display = ('swap_request', 'type', 'provider_tx_id', 'created_at')
    list_filter = ('type', 'created_at')
    readonly_fields = ('created_at',)

@admin.register(AgentWallet)
class AgentWalletAdmin(admin.ModelAdmin):
    list_display = ('agent', 'service_type', 'available_balance', 'total_earnings')
    list_filter = ('service_type',)