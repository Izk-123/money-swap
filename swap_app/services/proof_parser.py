import re
import pytesseract
from PIL import Image
from decimal import Decimal
from datetime import datetime

class ProofParser:
    """Service to parse proof images and SMS text for transaction verification"""
    
    @staticmethod
    def parse_sms(sms_text):
        """
        Parse SMS text to extract transaction details
        Returns dict with amount, reference, txid, account, confidence
        """
        sms_text = sms_text.upper().strip()
        
        # Mo626 patterns (National Bank)
        mo626_patterns = [
            r'RECEIVED MWK\s*([\d,]+\.\d{2})\s*FROM\s*(.+?)\.\s*REF:\s*(\w+)',
            r'DEPOSITED MWK\s*([\d,]+\.\d{2})\s*INTO YOUR ACCOUNT\.\s*REF:\s*(\w+)',
            r'TRANSACTION:\s*MWK\s*([\d,]+\.\d{2})\s*REF:\s*(\w+)\s*FROM\s*(.+)',
        ]
        
        # TNM Mpamba patterns
        tnm_patterns = [
            r'RECEIVED K\s*([\d,]+\.\d{2})\s*FROM\s*(\d+)\.\s*TXN ID:\s*(\w+)',
            r'SENT K\s*([\d,]+\.\d{2})\s*TO\s*(\d+)\.\s*TXN ID:\s*(\w+)',
        ]
        
        # Airtel Money patterns
        airtel_patterns = [
            r'RECEIVED\s*([\d,]+\.\d{2})\s*FROM\s*(\d+)\.\s*REF:\s*(\w+)',
            r'SENT\s*([\d,]+\.\d{2})\s*TO\s*(\d+)\.\s*REF:\s*(\w+)',
        ]
        
        # Standard Bank patterns
        standard_bank_patterns = [
            r'CREDIT\s*MWK\s*([\d,]+\.\d{2})\s*FROM\s*(.+?)\s*REF:\s*(\w+)',
            r'DEPOSIT\s*MWK\s*([\d,]+\.\d{2})\s*REF:\s*(\w+)',
        ]
        
        all_patterns = mo626_patterns + tnm_patterns + airtel_patterns + standard_bank_patterns
        
        for pattern in all_patterns:
            match = re.search(pattern, sms_text, re.IGNORECASE)
            if match:
                try:
                    amount_str = match.group(1).replace(',', '')
                    amount = Decimal(amount_str)
                    
                    # Determine provider based on which pattern matched
                    if pattern in mo626_patterns:
                        provider = 'mo626'
                        reference = match.group(3) if 'deposited' in sms_text.lower() else match.group(3)
                        account = match.group(2) if len(match.groups()) >= 3 else ''
                    elif pattern in tnm_patterns:
                        provider = 'tnm'
                        reference = match.group(3)
                        account = match.group(2)
                    elif pattern in airtel_patterns:
                        provider = 'airtel'
                        reference = match.group(3)
                        account = match.group(2)
                    else:  # standard_bank_patterns
                        provider = 'standard_bank'
                        reference = match.group(3) if len(match.groups()) >= 3 else match.group(2)
                        account = match.group(2) if len(match.groups()) >= 3 else ''
                    
                    return {
                        'amount': amount,
                        'reference': reference,
                        'txid': reference if provider in ['tnm', 'airtel'] else '',
                        'account': account,
                        'confidence': 0.9,
                        'provider': provider
                    }
                except (ValueError, IndexError, AttributeError):
                    continue
        
        # If no pattern matches, try to extract just the amount
        amount_match = re.search(r'MWK\s*([\d,]+\.\d{2})', sms_text, re.IGNORECASE)
        if not amount_match:
            amount_match = re.search(r'K\s*([\d,]+\.\d{2})', sms_text, re.IGNORECASE)
        
        if amount_match:
            try:
                amount_str = amount_match.group(1).replace(',', '')
                amount = Decimal(amount_str)
                return {
                    'amount': amount,
                    'reference': '',
                    'txid': '',
                    'account': '',
                    'confidence': 0.3,  # Low confidence since we only got amount
                    'provider': 'unknown'
                }
            except (ValueError, IndexError):
                pass
        
        return {'confidence': 0.0}
    
    @staticmethod
    def parse_image(image_file):
        """
        Extract text from proof images using OCR
        Then parse using SMS patterns
        """
        try:
            # Open and preprocess image
            image = Image.open(image_file)
            
            # Convert to grayscale for better OCR
            if image.mode != 'L':
                image = image.convert('L')
            
            # Use Tesseract OCR
            extracted_text = pytesseract.image_to_string(image)
            
            # Parse the extracted text
            return ProofParser.parse_sms(extracted_text)
            
        except Exception as e:
            print(f"OCR Error: {e}")
            return {'confidence': 0.0}
    
    @staticmethod
    def validate_proof(proof, swap):
        """
        Validate proof against swap details
        Returns (is_valid, errors, warnings)
        """
        errors = []
        warnings = []
        
        # Check amount match
        if proof.extracted_amount:
            if proof.extracted_amount != swap.amount:
                amount_diff = abs(proof.extracted_amount - swap.amount)
                if amount_diff <= Decimal('1.00'):  # Allow 1 MWK difference
                    warnings.append(f"Small amount difference: proof shows {proof.extracted_amount}, swap is {swap.amount}")
                else:
                    errors.append(f"Amount mismatch: proof shows {proof.extracted_amount}, swap is {swap.amount}")
        else:
            warnings.append("Could not extract amount from proof")
        
        # Check reference for bank transfers
        if (swap.from_service in ['national_bank', 'standard_bank', 'fdh_bank', 'nedbank'] and 
            proof.extracted_reference and 
            proof.extracted_reference != swap.reference):
            warnings.append(f"Reference mismatch: proof shows {proof.extracted_reference}, swap reference is {swap.reference}")
        
        # Check confidence score
        if proof.confidence_score < 0.5:
            warnings.append(f"Low confidence in proof parsing: {proof.confidence_score}")
        elif proof.confidence_score < 0.8:
            warnings.append(f"Moderate confidence in proof parsing: {proof.confidence_score}")
        
        return len(errors) == 0, errors, warnings
    
    @staticmethod
    def extract_transaction_details(text):
        """Extract transaction details from various SMS formats"""
        # Common transaction patterns in Malawi
        patterns = [
            # Amount patterns
            r'MWK\s*([\d,]+\.\d{2})',
            r'K\s*([\d,]+\.\d{2})',
            r'([\d,]+\.\d{2})\s*MWK',
            
            # Reference patterns
            r'REF:\s*(\w+)',
            r'REF\s*(\w+)',
            r'TXN ID:\s*(\w+)',
            r'ID:\s*(\w+)',
            
            # Account/Number patterns
            r'FROM\s*(\d+)',
            r'TO\s*(\d+)',
            r'ACCOUNT\s*(\w+)',
        ]
        
        results = {}
        for pattern in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            if matches:
                key = 'amount' if 'MWK' in pattern or 'K' in pattern else 'reference' if 'REF' in pattern or 'ID' in pattern else 'account'
                results[key] = matches[0]
        
        return results