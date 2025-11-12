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
    
    # Swap Management
    path('swap/<uuid:pk>/', views.SwapDetailView.as_view(), name='swap_detail'),
    path('swap/<uuid:pk>/upload-client-proof/', views.UploadClientProofView.as_view(), name='upload_client_proof'),
    path('swap/<uuid:pk>/upload-agent-proof/', views.UploadAgentProofView.as_view(), name='upload_agent_proof'),
    path('swap/<uuid:pk>/respond/', views.AgentResponseView.as_view(), name='agent_respond'),
    
    # Disputes
    path('swap/<uuid:pk>/create-dispute/', views.CreateDisputeView.as_view(), name='create_dispute'),
    
    # Agent Dashboard
    path('agent/dashboard/', views.AgentDashboardView.as_view(), name='agent_dashboard'),
    path('agent/toggle-online/', views.ToggleOnlineStatusView.as_view(), name='toggle_online'),
    
    # API Endpoints
    path('api/agent-recommendations/', views.AgentRecommendationAPIView.as_view(), name='agent_recommendations_api'),
    
    # UI
    path('toggle-theme/', views.ThemeToggleView.as_view(), name='toggle_theme'),
]