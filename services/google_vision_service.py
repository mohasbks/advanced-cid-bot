"""
Google Cloud Vision API Service for OCR
High-accuracy OCR with smart text detection and filtering
"""
import os
import re
import logging
from typing import List, Dict, Tuple, Optional
from google.cloud import vision
from google.oauth2 import service_account

logger = logging.getLogger(__name__)

class GoogleVisionService:
    """Google Cloud Vision API for high-accuracy OCR"""
    
    def __init__(self, credentials_path: str = None, credentials_json: str = None):
        """Initialize Google Vision client"""
        try:
            if credentials_json:
                # Load credentials from JSON string (Railway deployment)
                import json
                credentials_info = json.loads(credentials_json)
                credentials = service_account.Credentials.from_service_account_info(
                    credentials_info,
                    scopes=[
                        'https://www.googleapis.com/auth/cloud-platform',
                        'https://www.googleapis.com/auth/cloud-vision'
                    ]
                )
                logger.info("Google Vision API initialized from JSON credentials")
                
            elif credentials_path:
                # Load credentials from JSON file (local development)
                os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = credentials_path
                credentials = service_account.Credentials.from_service_account_file(
                    credentials_path,
                    scopes=[
                        'https://www.googleapis.com/auth/cloud-platform',
                        'https://www.googleapis.com/auth/cloud-vision'
                    ]
                )
                logger.info("Google Vision API initialized from file credentials")
                
            else:
                raise ValueError("Either credentials_path or credentials_json must be provided")
            
            # Initialize the client
            self.client = vision.ImageAnnotatorClient(credentials=credentials)
            logger.info(f"Google Vision API client initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize Google Vision API: {e}")
            raise
    
    def extract_installation_id(self, image_path: str) -> Dict:
        """
        Extract Installation ID from image using Google Vision API
        Looks for 7-9 groups of exactly 7 digits each
        Returns dict with extracted text, confidence, and validation status
        """
        try:
            # Read image file
            with open(image_path, 'rb') as image_file:
                content = image_file.read()
            
            # Create vision image object
            image = vision.Image(content=content)
            
            # Perform text detection
            response = self.client.text_detection(image=image)
            
            if response.error.message:
                raise Exception(f"Vision API error: {response.error.message}")
            
            # Extract text annotations
            texts = response.text_annotations
            
            if not texts:
                return {
                    'success': False,
                    'error': 'No text detected in image',
                    'installation_id': '',
                    'confidence': 0.0
                }
            
            # Extract 7-digit groups using exact user method
            seven_digit_numbers = [t.description for t in texts if re.fullmatch(r"\d{7}", t.description)]
            
            # Check if we found 7-9 groups
            if len(seven_digit_numbers) in [7, 8, 9]:
                # Join groups to form complete Installation ID
                installation_id = ''.join(seven_digit_numbers)
                
                return {
                    'success': True,
                    'installation_id': installation_id,
                    'confidence': 0.95,
                    'groups_found': len(seven_digit_numbers),
                    'groups': seven_digit_numbers,
                    'method': 'exact-user-method'
                }
            else:
                return {
                    'success': False,
                    'error': f'Did not find the expected 7–9 groups of 7 digits (found {len(seven_digit_numbers)} groups)',
                    'installation_id': '',
                    'confidence': 0.0,
                    'groups_found': len(seven_digit_numbers)
                }
        
        except Exception as e:
            logger.error(f"Error in Google Vision OCR: {e}")
            return {
                'success': False,
                'error': str(e),
                'installation_id': '',
                'confidence': 0.0
            }
    
    def _calculate_confidence(self, text_annotation) -> float:
        """Calculate confidence score from text annotation"""
        try:
            # Vision API doesn't directly provide confidence for text detection
            # We estimate based on bounding box quality and text clarity
            vertices = text_annotation.bounding_poly.vertices
            
            if len(vertices) == 4:
                # Well-formed bounding box = higher confidence
                return 0.95
            else:
                return 0.85
        except:
            return 0.8
    
    def _find_installation_id_candidates(self, text_annotations: List) -> List[Dict]:
        """Find potential Installation ID candidates from text annotations"""
        candidates = []
        
        for annotation in text_annotations:
            text = annotation.description.strip()
            
            # Clean text (remove spaces, special chars)
            clean_text = re.sub(r'[^0-9]', '', text)
            
            # Skip if too short for Installation ID
            if len(clean_text) < 40:
                continue
                
            # Skip obvious non-Installation ID patterns
            if self._is_likely_non_installation_id(clean_text, text):
                continue
            
            # Only accept if it looks like Installation ID
            if self._looks_like_installation_id(text):
                # Calculate confidence for this annotation
                confidence = self._calculate_confidence(annotation)
                
                # Calculate position score (prefer center/bottom area)
                position_score = self._calculate_position_score(annotation.bounding_poly)
                
                # Calculate size score (prefer larger text)
                size_score = self._calculate_size_score(annotation.bounding_poly)
                
                # Combine all scores
                final_confidence = confidence * position_score * size_score
                
                # Boost confidence for texts that look like Installation IDs
                final_confidence *= 1.5
                
                candidates.append({
                    'text': clean_text,
                    'original': text,
                    'confidence': final_confidence,
                    'position_score': position_score,
                    'size_score': size_score,
                    'length': len(clean_text)
                })
        
        # Sort by confidence score
        candidates.sort(key=lambda x: x['confidence'], reverse=True)
        
        return candidates
    
    def _calculate_position_score(self, bounding_poly) -> float:
        """Calculate position score - prefer center-bottom, avoid top-right"""
        try:
            vertices = bounding_poly.vertices
            if len(vertices) < 2:
                return 0.5
            
            # Get center point
            center_x = sum(v.x for v in vertices) / len(vertices)
            center_y = sum(v.y for v in vertices) / len(vertices)
            
            # Assume image dimensions (will be improved with actual dimensions)
            img_width = 1000  # Estimated
            img_height = 800   # Estimated
            
            # Strongly penalize top-right area (where dates/steps usually are)
            if center_x > 0.7 * img_width and center_y < 0.3 * img_height:
                return 0.2  # Very low score for top-right
                
            # Penalize top area in general
            if center_y < 0.2 * img_height:
                return 0.4  # Low score for top area
            
            # Prefer center horizontally (0.2-0.8 of width)
            horizontal_score = 1.0 if 0.2 * img_width <= center_x <= 0.8 * img_width else 0.6
            
            # Strongly prefer middle to bottom (0.3-0.9 of height)  
            if 0.5 * img_height <= center_y <= 0.9 * img_height:
                vertical_score = 1.2  # Boost for ideal area
            elif 0.3 * img_height <= center_y <= 0.5 * img_height:
                vertical_score = 1.0  # Good area
            else:
                vertical_score = 0.5  # Less preferred
            
            return (horizontal_score + vertical_score) / 2
            
        except:
            return 0.5
    
    def _calculate_size_score(self, bounding_poly) -> float:
        """Calculate size score - prefer larger text"""
        try:
            vertices = bounding_poly.vertices
            if len(vertices) < 2:
                return 0.5
            
            # Calculate approximate width and height
            width = max(v.x for v in vertices) - min(v.x for v in vertices)
            height = max(v.y for v in vertices) - min(v.y for v in vertices)
            
            # Prefer larger text (installation IDs are usually prominent)
            area = width * height
            
            if area > 10000:
                return 1.0
            elif area > 5000:
                return 0.8
            elif area > 2000:
                return 0.6
            else:
                return 0.4
                
        except:
            return 0.5
    
    def _looks_like_installation_id(self, text: str) -> bool:
        """Check if text looks like an Installation ID"""
        # Skip if contains Arabic text patterns (like "خطوة 1", "Step 1", etc.)
        if re.search(r'[\u0600-\u06FF]', text):  # Arabic unicode range
            return False
            
        # Skip if contains common UI text patterns
        ui_patterns = ['step', 'خطوة', 'الخطوة', 'Step', 'STEP']
        for pattern in ui_patterns:
            if pattern.lower() in text.lower():
                return False
        
        # Remove all non-digits
        digits = re.sub(r'[^0-9]', '', text)
        
        # Must have at least 50 digits for Installation ID
        if len(digits) < 50:
            return False
            
        # Check if it has good digit variety (not all same digits)
        unique_digits = len(set(digits))
        if unique_digits < 6:  # At least 6 different digits
            return False
        
        # Check for grouped patterns like: 1234567-1234567-1234567...
        if re.search(r'\d{6,7}[\s\-]\d{6,7}[\s\-]\d{6,7}', text):
            return True
            
        # Check for long continuous digit sequence (50+ digits)
        if len(digits) >= 50:
            return True
            
        return False
    
    def _is_likely_non_installation_id(self, clean_text: str, original_text: str) -> bool:
        """Check if text is likely NOT an Installation ID"""
        
        # Skip phone numbers (Saudi Arabia patterns)
        phone_patterns = [
            r'^(\+?966|0966|966)\d{8,9}$',  # Saudi numbers
            r'^05\d{8}$',  # Mobile numbers
            r'^01\d{8}$',  # Landline numbers
            r'^00966\d{8,9}$'  # International format
        ]
        
        for pattern in phone_patterns:
            if re.match(pattern, clean_text):
                return True
                
        # Skip if starts with phone number patterns
        if clean_text.startswith(('00966', '966', '05', '01', '+966')):
            return True
            
        # Skip specific problematic patterns (exact matches only)
        if clean_text.startswith(('2021', '0211', '211')):
            return True
            
        # Skip if original text contains Arabic or UI text
        if re.search(r'[\u0600-\u06FF]', original_text):  # Arabic unicode
            return True
            
        # Skip if contains UI step indicators
        ui_indicators = ['step', 'خطوة', 'الخطوة', 'Step', 'STEP']
        for indicator in ui_indicators:
            if indicator.lower() in original_text.lower():
                return True
            
        # Skip if too much repetition (likely formatting artifacts)
        if re.search(r'(\d)\1{10,}', clean_text):  # 11+ same digits
            return True
            
        # Skip if too few unique digits (likely serial numbers or codes)
        if len(set(clean_text)) < 4:
            return True
            
        # Skip very short sequences
        if len(clean_text) < 40:
            return True
            
        return False
    
    def _select_best_candidate(self, candidates: List[Dict]) -> Optional[Dict]:
        """Select the best Installation ID candidate with improved logic"""
        
        # Filter out obviously wrong candidates
        filtered_candidates = []
        for candidate in candidates:
            text = candidate['text']
            
            # Skip very short sequences
            if len(text) < 50:
                continue
            
            # Skip sequences with too few unique digits
            if len(set(text)) < 6:
                continue
                
            # Skip obvious patterns like phone numbers
            if text.startswith(('00966', '966', '+966', '05', '01')):
                continue
                
            # Skip specific problematic patterns (exact matches only)
            if text.startswith(('2021', '0211', '211')):
                continue
                
            filtered_candidates.append(candidate)
        
        candidates = filtered_candidates
        
        if not candidates:
            return None
        
        # Score each candidate based on Installation ID characteristics
        for candidate in candidates:
            text = candidate['text']
            score = candidate['confidence']
            
            # Boost score for optimal length (60-66 digits)
            if 60 <= len(text) <= 66:
                score *= 1.5
            elif 55 <= len(text) <= 70:
                score *= 1.2
            
            # Boost score for good digit variety
            unique_digits = len(set(text))
            if unique_digits >= 8:
                score *= 1.3
            elif unique_digits >= 6:
                score *= 1.1
            
            # Penalize patterns that look like concatenated numbers
            if re.search(r'(\d)\1{5,}', text):  # 6+ same digits in a row
                score *= 0.7
                
            # Boost score for Installation ID-like patterns
            if not text.startswith(('0000', '1111', '2222')):
                score *= 1.1
                
            candidate['final_score'] = score
        
        # Sort by final score and return best
        candidates.sort(key=lambda x: x['final_score'], reverse=True)
        
        best = candidates[0]
        
        # If the best candidate is longer than 63, extract best 63-digit substring
        if len(best['text']) > 63:
            best_substring = self._find_best_63_digit_substring(best['text'])
            if best_substring:
                best['text'] = best_substring
        
        return best
    
    def _extract_from_full_text(self, full_text: str) -> Optional[str]:
        """Fallback: extract 63-digit sequence from full text"""
        
        # Remove all non-digits
        digits_only = re.sub(r'[^0-9]', '', full_text)
        
        # Look for 63-digit sequence
        if len(digits_only) == 63:
            # Apply same filtering as candidates
            if self._is_likely_non_installation_id(digits_only, digits_only):
                return None
            return digits_only
        elif len(digits_only) > 63:
            # Score all possible 63-digit substrings and pick the best
            best_candidate = None
            best_score = 0
            
            for i in range(len(digits_only) - 62):
                candidate = digits_only[i:i+63]
                
                # Apply filtering: skip problematic patterns
                if self._is_likely_non_installation_id(candidate, candidate):
                    continue
                    
                # Additional check: skip specific problematic patterns
                if candidate.startswith(('2021', '0211', '211')):
                    continue
                    
                # Skip if starts with too many zeros
                if candidate.startswith('0000'):
                    continue
                
                # Score this candidate
                score = 0
                
                # Prefer high digit variety
                unique_digits = len(set(candidate))
                score += unique_digits * 3
                
                # Prefer candidates that don't start with obvious problematic patterns
                if not candidate.startswith(('000', '111', '222')):
                    score += 10
                    
                # Avoid too much repetition
                if not re.search(r'(\d)\1{4,}', candidate):  # No 5+ repeated digits
                    score += 5
                    
                # Prefer candidates from middle/end of string (skip prefixes)
                if i > len(digits_only) * 0.1:  # Skip first 10% of string
                    score += 5
                
                if score > best_score:
                    best_score = score
                    best_candidate = candidate
            
            return best_candidate
        
        return None
    
    def _find_best_63_digit_substring(self, text: str) -> Optional[str]:
        """Find the best 63-digit substring with enhanced scoring"""
        if len(text) < 63:
            return None
            
        best_score = 0
        best_substring = None
        
        # Try different starting positions
        for i in range(len(text) - 62):
            substring = text[i:i+63]
            
            # Skip problematic patterns immediately
            if self._is_likely_non_installation_id(substring, substring):
                continue
            
            # Score this substring
            score = 0
            
            # Prefer substrings with excellent digit variety
            unique_count = len(set(substring))
            score += unique_count * 4  # Higher weight for variety
            
            # Avoid substrings that start with obvious problematic patterns
            if not substring.startswith(('000', '111', '222', '333')):
                score += 15
            
            # Prefer substrings that don't have too many repeating patterns
            if not re.search(r'(\d)\1{4,}', substring):  # No 5+ repeated digits
                score += 10
                
            # Avoid specific problematic patterns at START only
            if not substring.startswith(('2021', '0211', '211')):
                score += 10
                
            # Prefer positions that skip obvious prefixes
            if i > 0:  # Not at the very beginning
                score += 5
                
            if score > best_score:
                best_score = score
                best_substring = substring
        
        return best_substring if best_score > 25 else None
    
    def validate_installation_id(self, installation_id: str) -> Dict:
        """Validate extracted Installation ID"""
        
        # Remove any non-digits
        clean_id = re.sub(r'[^0-9]', '', installation_id)
        
        validation = {
            'is_valid': False,
            'cleaned_id': clean_id,
            'issues': []
        }
        
        # Check length
        if len(clean_id) != 63:
            validation['issues'].append(f"Wrong length: {len(clean_id)} (expected 63)")
        
        # Check for obvious invalid patterns
        if clean_id.startswith('000000'):
            validation['issues'].append("Starts with too many zeros")
            
        if clean_id.startswith(('00966', '966', '+966', '05', '01')):
            validation['issues'].append("Looks like a phone number")
        
        if len(set(clean_id)) < 5:  # Too few unique digits
            validation['issues'].append("Too few unique digits")
            
        # Check for too much repetition
        if re.search(r'(\d)\1{8,}', clean_id):  # 9+ same digits in a row
            validation['issues'].append("Too much digit repetition")
        
        # If no issues, it's valid
        if not validation['issues'] and len(clean_id) == 63:
            validation['is_valid'] = True
        
        return validation
    
    def _extract_seven_digit_groups(self, text_annotations: List) -> List[str]:
        """
        Extract exactly 9 groups of 7 digits from text annotations (63 digits total)
        Returns list of exactly 9 groups or empty list
        """
        
        # Get full text first - this is our primary source
        if not text_annotations:
            return []
            
        full_text = text_annotations[0].description
        
        # Find groups in full text using improved method
        groups = self._find_groups_in_text(full_text)
        
        # Must have exactly 9 groups for valid Installation ID
        if len(groups) == 9:
            return groups
        else:
            return []
    
    def _find_groups_in_text(self, text: str) -> List[str]:
        """Find exactly 9 groups of 7 digits in a text string"""
        
        # Remove all non-digits first  
        digits_only = re.sub(r'[^0-9]', '', text)
        
        # Need at least 63 digits
        if len(digits_only) < 63:
            return []
        
        # If exactly 63 digits, split directly
        if len(digits_only) == 63:
            groups = []
            for i in range(0, 63, 7):
                group = digits_only[i:i+7]
                groups.append(group)
            return groups
        
        # If more than 63 digits, find the best 63-digit sequence
        if len(digits_only) > 63:
            # Try different starting positions to find valid 63-digit sequence
            for start in range(len(digits_only) - 62):
                candidate_63 = digits_only[start:start+63]
                
                # Check if this 63-digit sequence looks valid
                if self._is_valid_63_digit_sequence(candidate_63):
                    groups = []
                    for i in range(0, 63, 7):
                        group = candidate_63[i:i+7]
                        groups.append(group)
                    return groups
        
        return []
    
    def _is_valid_63_digit_sequence(self, sequence: str) -> bool:
        """Check if a 63-digit sequence looks like a valid Installation ID"""
        
        # Must be exactly 63 digits
        if len(sequence) != 63 or not sequence.isdigit():
            return False
        
        # Skip sequences that start with obvious invalid patterns
        if sequence.startswith(('00966', '966', '05', '01', '000000', '111111')):
            return False
        
        # Skip sequences with too much repetition
        if re.search(r'(\d)\1{10,}', sequence):  # 11+ same digits in a row
            return False
        
        # Must have good digit variety
        unique_digits = len(set(sequence))
        if unique_digits < 6:  # Need at least 6 different digits
            return False
        
        return True
    
    def _is_valid_seven_digit_group(self, group: str) -> bool:
        """Validate if a 7-digit group looks like part of an Installation ID"""
        
        # Must be exactly 7 digits
        if len(group) != 7 or not group.isdigit():
            return False
        
        # Skip groups that are likely not Installation ID parts
        
        # Skip groups with too much repetition
        if re.match(r'^(\d)\1{6}$', group):  # All same digit
            return False
        if re.match(r'^(\d)\1{4,}', group):  # 5+ same digits at start
            return False
        
        # Skip obvious sequential patterns
        if group in ['1234567', '0123456', '9876543']:
            return False
        
        # Skip groups that look like phone number parts
        if group.startswith(('0096650', '096650', '96650', '0500000', '0540000')):
            return False
        
        # Skip groups with too few unique digits
        if len(set(group)) < 4:
            return False
        
        # Skip groups that are all zeros or start with many zeros
        if group.startswith('0000'):
            return False
        
        # This looks like a valid 7-digit group
        return True
    
    def _sort_groups_by_likelihood(self, groups: List[str]) -> List[str]:
        """Sort groups by likelihood of being correct Installation ID parts"""
        
        def group_score(group: str) -> float:
            score = 0.0
            
            # Prefer groups with good digit variety
            unique_digits = len(set(group))
            score += unique_digits * 2
            
            # Prefer groups that don't start with 0
            if not group.startswith('0'):
                score += 5
            
            # Prefer groups without too much repetition
            if not re.search(r'(\d)\1{2,}', group):  # No 3+ repeated digits
                score += 3
            
            # Slightly prefer groups that don't have obvious patterns
            if not re.search(r'(012|123|234|345|456|567|678|789|987|876|765|654|543|432|321|210)', group):
                score += 1
            
            return score
        
        # Sort by score (highest first)
        return sorted(groups, key=group_score, reverse=True)
    
    def _calculate_groups_confidence(self, groups: List[str], text_annotations: List) -> float:
        """Calculate confidence based on the quality and count of 7-digit groups found"""
        
        if not groups:
            return 0.0
        
        base_confidence = 0.8
        group_count = len(groups)
        
        # Adjust confidence based on group count
        if 7 <= group_count <= 9:
            # Ideal count for Installation ID (49-63 digits)
            count_multiplier = 1.0
        elif 5 <= group_count <= 6:
            # Acceptable but not ideal
            count_multiplier = 0.9
        elif 4 <= group_count:
            # Too few groups
            count_multiplier = 0.7
        else:
            # Too few groups
            count_multiplier = 0.5
        
        # Check quality of groups
        quality_score = 0.0
        for group in groups:
            # Score each group
            unique_digits = len(set(group))
            if unique_digits >= 6:
                quality_score += 1.0
            elif unique_digits >= 4:
                quality_score += 0.8
            else:
                quality_score += 0.5
        
        # Average quality
        if groups:
            quality_multiplier = quality_score / len(groups)
        else:
            quality_multiplier = 0.5
        
        # Final confidence calculation
        final_confidence = base_confidence * count_multiplier * quality_multiplier
        
        # Cap at 0.95
        return min(final_confidence, 0.95)
    
    def _fallback_to_old_method(self, text_annotations: List) -> Optional[Dict]:
        """Fallback to the original method if 7-digit groups approach fails"""
        
        if not text_annotations:
            return None
        
        # Get full text (first annotation contains all text)
        full_text = text_annotations[0].description
        overall_confidence = self._calculate_confidence(text_annotations[0])
        
        # Find Installation ID candidates using old method
        candidates = self._find_installation_id_candidates(text_annotations[1:])  # Skip full text
        
        if candidates:
            # Choose best candidate
            best_candidate = self._select_best_candidate(candidates)
            
            return {
                'success': True,
                'installation_id': best_candidate['text'],
                'confidence': best_candidate['confidence'] * 0.8,  # Lower confidence for fallback
                'full_text': full_text,
                'candidates_count': len(candidates),
                'method': 'fallback_old'
            }
        else:
            # Try to extract from full text
            fallback_id = self._extract_from_full_text(full_text)
            
            if fallback_id:
                return {
                    'success': True,
                    'installation_id': fallback_id,
                    'confidence': overall_confidence * 0.6,  # Lower confidence for full fallback
                    'full_text': full_text,
                    'method': 'fallback_full_text'
                }
        
        return None
