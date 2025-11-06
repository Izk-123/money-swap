from django.urls import path
from . import views

urlpatterns = [
    # Public URLs
    path('', views.HomeView.as_view(), name='home'),
    path('register/', views.RegisterView.as_view(), name='register'),
    
    # Dashboard & Notifications
    path('dashboard/', views.DashboardView.as_view(), name='dashboard'),
    path('notifications/', views.NotificationListView.as_view(), name='notifications'),
    
    # Agent Selection & Swaps
    path('agents/', views.AgentListView.as_view(), name='agent_list'),
    path('create-swap/', views.CreateSwapView.as_view(), name='create_swap'),
    path('my-swaps/', views.ClientSwapRequestsView.as_view(), name='client_swaps'),
    
    # Account Management
    path('my-accounts/', views.AccountListView.as_view(), name='my_accounts'),
    path('my-accounts/add/', views.AccountCreateView.as_view(), name='add_account'),
    path('account/<int:pk>/deactivate/', views.DeactivateAccountView.as_view(), name='deactivate_account'),
    path('account/<int:pk>/activate/', views.ActivateAccountView.as_view(), name='activate_account'),
    path('account/<int:pk>/edit/', views.EditAccountView.as_view(), name='edit_account'),
    
    # Swap Management
    path('swap/<uuid:pk>/', views.SwapDetailView.as_view(), name='swap_detail'),
    path('swap/<uuid:pk>/upload-proof/', views.UploadProofView.as_view(), name='upload_proof'),
    path('swap/<uuid:pk>/agent-send/', views.AgentSendView.as_view(), name='agent_send'),
    path('swap/<uuid:pk>/complete/', views.CompleteSwapView.as_view(), name='complete_swap'),
    path('swap/<uuid:pk>/respond/', views.AgentResponseView.as_view(), name='agent_respond'),
    
    # Agent Dashboard
    path('agent/dashboard/', views.AgentDashboardView.as_view(), name='agent_dashboard'),
    path('agent/transactions/', views.AgentTransactionsView.as_view(), name='agent_transactions'),
    path('agent/wallet/', views.AgentWalletView.as_view(), name='agent_wallet'),
    
    # Location & Online Status
    path('update-location/', views.UpdateLocationView.as_view(), name='update_location'),
    path('get-distance/', views.GetDistanceView.as_view(), name='get_distance'),
    path('agent/toggle-online/', views.ToggleOnlineStatusView.as_view(), name='toggle_online'),
    
    # Webhooks
    path('webhook/bank/', views.webhook_bank, name='webhook_bank'),
    path('webhook/wallet/', views.webhook_wallet, name='webhook_wallet'),
    
    # UI
    path('toggle-theme/', views.ThemeToggleView.as_view(), name='toggle_theme'),
]