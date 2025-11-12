from django.utils import timezone

class ComplianceService:
    """Service to ensure platform operates within legal boundaries - NO MONEY HOLDING"""
    
    @staticmethod
    def generate_terms_of_service():
        """Generate platform terms emphasizing no money holding"""
        return {
            'platform_name': 'MoneySwap',
            'legal_status': 'Technology Service Provider',
            'key_points': [
                "MoneySwap acts as a matching service only between clients and agents",
                "All financial transactions occur directly between users",
                "Platform never holds, stores, or transfers user funds",
                "Fees are for matching and verification services only",
                "Users are responsible for their own financial transactions",
                "Platform provides dispute resolution as a service",
                "No escrow services are provided"
            ],
            'compliance_notes': [
                "Not a financial institution under RBM regulations",
                "Not a payment service provider",
                "No money transmission services",
                "No banking or financial services license required",
                "Operates as technology platform under general business laws"
            ],
            'fee_structure': {
                'total_fee': '0.6% (minimum MWK 50)',
                'platform_portion': '0.15% (billed monthly via invoice)',
                'agent_portion': '0.45% (retained by agent)',
                'settlement': 'Monthly invoicing for platform fees'
            }
        }
    
    @staticmethod
    def generate_user_agreement(user):
        """Generate user-specific agreement"""
        return f"""
        MONEYSWAP USER AGREEMENT
        
        User Information:
        - Username: {user.username}
        - Role: {user.get_role_display()}
        - Phone: {user.phone_number}
        - Agreement Date: {timezone.now().strftime('%Y-%m-%d')}
        
        IMPORTANT TERMS AND CONDITIONS:
        
        1. SERVICE NATURE
        MoneySwap provides matching and verification services only.
        The platform connects clients with verified agents for money swapping.
        
        2. NO MONEY HOLDING
        MoneySwap NEVER holds, stores, or transmits user funds.
        All financial transactions occur directly between you and other users.
        
        3. USER RESPONSIBILITIES
        You are solely responsible for:
        - Verifying transaction details before sending money
        - Ensuring you send to correct recipient details
        - Keeping transaction proofs and records
        - Reporting issues within 24 hours
        
        4. FEE STRUCTURE
        Total service fee: 0.6% of swap amount (minimum MWK 50)
        - Platform portion: 0.15% (billed monthly via invoice)
        - Agent portion: 0.45% (retained by agent)
        
        5. DISPUTE RESOLUTION
        Platform provides dispute resolution services but:
        - No financial guarantees are provided
        - Resolution is based on available evidence
        - Platform decisions are final
        
        6. LEGAL STATUS
        MoneySwap is not regulated by RBM as we do not:
        - Accept deposits from users
        - Provide payment transmission services
        - Hold user funds in escrow or otherwise
        - Operate as a financial institution
        
        7. RISK ACKNOWLEDGEMENT
        You acknowledge that:
        - All transactions are between you and other users
        - Platform only facilitates matching and verification
        - You bear responsibility for your financial decisions
        - Platform liability is limited to service fees
        
        By using this platform, you acknowledge and agree to these terms.
        
        User Signature: _________________________
        Date: {timezone.now().strftime('%Y-%m-%d')}
        """
    
    @staticmethod
    def generate_agent_agreement(agent):
        """Generate agent-specific agreement"""
        return f"""
        MONEYSWAP AGENT AGREEMENT
        
        Agent Information:
        - Username: {agent.user.username}
        - Business Name: {agent.user.get_full_name() or agent.user.username}
        - Phone: {agent.user.phone_number}
        - Agreement Date: {timezone.now().strftime('%Y-%m-%d')}
        
        AGENT TERMS AND CONDITIONS:
        
        1. AGENT ROLE
        You act as an independent service provider using MoneySwap platform.
        You are not an employee of MoneySwap.
        
        2. FINANCIAL ARRANGEMENTS
        - You maintain your own bank/mobile money accounts
        - You receive payments directly from clients
        - You send payments directly to clients
        - You retain 0.45% of each swap as your service fee
        
        3. PLATFORM FEES
        - Platform fee: 0.15% of swap amount
        - Billed monthly via invoice
        - Due within 30 days of invoice date
        
        4. AGENT RESPONSIBILITIES
        You are responsible for:
        - Maintaining sufficient liquidity for swaps
        - Responding to swap requests promptly
        - Verifying client payments before sending
        - Providing accurate payment details to clients
        - Keeping proper transaction records
        
        5. COMPLIANCE REQUIREMENTS
        You must:
        - Operate within applicable laws and regulations
        - Maintain valid identification documents
        - Report any suspicious activities
        - Cooperate with dispute resolution processes
        
        6. TERMINATION
        Platform may suspend or terminate your agent status for:
        - Fraudulent activities
        - Multiple justified complaints
        - Failure to pay platform fees
        - Violation of terms of service
        
        Agent Signature: _________________________
        Date: {timezone.now().strftime('%Y-%m-%d')}
        """
    
    @staticmethod
    def generate_regulatory_disclaimer():
        """Generate regulatory disclaimer for public facing materials"""
        return """
        REGULATORY DISCLAIMER
        
        MoneySwap operates as a technology platform providing matching and verification services.
        
        IMPORTANT NOTES:
        
        1. NON-FINANCIAL STATUS
        MoneySwap is not a financial institution, bank, payment service provider, 
        or money transmission business as defined by the Reserve Bank of Malawi.
        
        2. NO FUNDS HANDLING
        The platform does not accept, hold, or transmit user funds. All financial 
        transactions occur directly between users.
        
        3. SERVICE NATURE
        We provide:
        - Matching between clients and agents
        - Transaction verification services
        - Dispute resolution facilitation
        - Record keeping and reporting
        
        4. USER RESPONSIBILITY
        Users are solely responsible for their financial transactions and must 
        verify all transaction details before proceeding.
        
        5. COMPLIANCE
        MoneySwap operates in compliance with general business laws and 
        technology service provider regulations in Malawi.
        
        For regulatory inquiries, contact: compliance@moneyswap.mw
        """
    
    @staticmethod
    def check_swap_compliance(swap):
        """Check if swap complies with platform rules"""
        violations = []
        
        # Amount limits
        from django.conf import settings
        min_amount = getattr(settings, 'MIN_SWAP_AMOUNT', 50)
        max_amount = getattr(settings, 'MAX_SWAP_AMOUNT', 50000)
        
        if swap.amount < min_amount:
            violations.append(f"Amount below minimum: MWK {swap.amount} < MWK {min_amount}")
        
        if swap.amount > max_amount:
            violations.append(f"Amount above maximum: MWK {swap.amount} > MWK {max_amount}")
        
        # User limits
        if swap.client.todays_swap_volume + swap.amount > swap.client.daily_swap_limit:
            violations.append(f"Would exceed client's daily limit")
        
        # Agent capacity
        if not swap.agent.can_accept_swap:
            violations.append("Agent has reached daily swap capacity")
        
        return len(violations) == 0, violations