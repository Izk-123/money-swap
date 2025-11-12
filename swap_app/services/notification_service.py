from django.conf import settings
from ..tasks import send_sms_notification, send_email_notification, send_whatsapp_notification

class NotificationService:
    """Service for sending various types of notifications"""
    
    @staticmethod
    def notify_agent_new_swap(swap):
        """Notify agent about new swap request"""
        message = f"New swap request: MWK {swap.amount} from {swap.client.username}. Reference: {swap.reference}"
        
        # Send SMS
        try:
            send_sms_notification.delay(swap.agent.user.phone_number, message)
        except Exception as e:
            print(f"Failed to send SMS: {e}")
        
        # Send email
        if swap.agent.user.email:
            email_subject = f"New Swap Request - {swap.reference}"
            email_message = f"""
            You have a new swap request from {swap.client.username}.
            
            Details:
            - Amount: MWK {swap.amount}
            - From: {swap.from_service}
            - To: {swap.to_service}
            - Reference: {swap.reference}
            
            Please respond within 30 minutes.
            """
            send_email_notification.delay(swap.agent.user.email, email_subject, email_message)
    
    @staticmethod
    def notify_client_swap_accepted(swap):
        """Notify client that swap was accepted"""
        message = f"Agent {swap.agent.user.username} accepted your swap request. Please send MWK {swap.amount} to their account."
        
        # Get agent payment details
        payment_details = swap.agent.get_payment_details(swap.from_service)
        
        # Send SMS with payment instructions
        if payment_details:
            if payment_details['type'] == 'bank':
                payment_instructions = f"Send to: {payment_details['bank_name']} Acc: {payment_details['account_number']}"
            else:
                payment_instructions = f"Send to: {payment_details['provider']} {payment_details['number']}"
            
            full_message = f"{message} {payment_instructions}. Ref: {swap.reference}"
        else:
            full_message = f"{message} Reference: {swap.reference}"
        
        try:
            send_sms_notification.delay(swap.client.phone_number, full_message)
        except Exception as e:
            print(f"Failed to send SMS: {e}")
    
    @staticmethod  
    def notify_swap_completed(swap):
        """Notify both parties that swap is complete"""
        client_message = f"Swap {swap.reference} completed! You received MWK {swap.net_amount} on your {swap.to_service}."
        agent_message = f"Swap {swap.reference} completed! You earned MWK {swap.agent_fee} in agent fees."
        
        try:
            send_sms_notification.delay(swap.client.phone_number, client_message)
            send_sms_notification.delay(swap.agent.user.phone_number, agent_message)
        except Exception as e:
            print(f"Failed to send completion SMS: {e}")
    
    @staticmethod
    def notify_dispute_opened(dispute):
        """Notify relevant parties about dispute"""
        swap = dispute.swap_request
        message = f"Dispute opened for swap {swap.reference}. Severity: {dispute.severity}. Reason: {dispute.reason[:50]}..."
        
        # Notify both parties
        parties = [swap.client, swap.agent.user]
        for party in parties:
            try:
                send_sms_notification.delay(party.phone_number, f"Dispute alert: {message}")
            except Exception as e:
                print(f"Failed to send dispute SMS: {e}")
    
    @staticmethod
    def notify_kyc_status(user, status, reason=""):
        """Notify user about KYC verification status"""
        if status == 'approved':
            message = "Your KYC verification has been approved! You can now use all platform features."
        else:
            message = f"Your KYC verification was rejected. Reason: {reason}. Please submit new documents."
        
        try:
            send_sms_notification.delay(user.phone_number, message)
        except Exception as e:
            print(f"Failed to send KYC status SMS: {e}")
        
        if user.email:
            subject = "KYC Verification Status Update"
            send_email_notification.delay(user.email, subject, message)
    
    @staticmethod
    def notify_monthly_statement(user, statement_data):
        """Send monthly statement to user"""
        if user.email:
            subject = f"MoneySwap Monthly Statement - {statement_data['period']}"
            message = f"""
            Monthly Statement for {statement_data['period']}
            
            Summary:
            - Total Swaps: {statement_data['total_swaps']}
            - Total Volume: MWK {statement_data['total_volume']:,.2f}
            - Platform Fees: MWK {statement_data['platform_fees']:,.2f}
            - Agent Earnings: MWK {statement_data['agent_earnings']:,.2f}
            
            Thank you for using MoneySwap!
            """
            send_email_notification.delay(user.email, subject, message)