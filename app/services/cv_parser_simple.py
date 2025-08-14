import re
from typing import List, Dict, Tuple
from docx import Document
import PyPDF2
from datetime import datetime
import io
import logging

logger = logging.getLogger(__name__)

class CVParser:
    def __init__(self):
        # Simple parser without spaCy dependency
        self.use_spacy = False
        logger.info("CV Parser initialized in simple mode (no spaCy)")
    
    def parse_pdf(self, file_content: bytes) -> str:
        """Extract text from PDF file"""
        try:
            pdf_reader = PyPDF2.PdfReader(io.BytesIO(file_content))
            text = ""
            for page in pdf_reader.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
            return text.strip()
        except Exception as e:
            logger.error(f"Error parsing PDF: {e}")
            return ""
    
    def parse_docx(self, file_content: bytes) -> str:
        """Extract text from DOCX file"""
        try:
            doc = Document(io.BytesIO(file_content))
            text = ""
            for paragraph in doc.paragraphs:
                text += paragraph.text + "\n"
            return text.strip()
        except Exception as e:
            logger.error(f"Error parsing DOCX: {e}")
            return ""
    
    def extract_contact_info(self, text: str) -> Dict[str, str]:
        """Extract contact information from CV text"""
        contact_info = {}
        
        # Email pattern
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        emails = re.findall(email_pattern, text)
        if emails:
            contact_info['email'] = emails[0]
        
        # Phone pattern (various formats)
        phone_pattern = r'(\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}'
        phones = re.findall(phone_pattern, text)
        if phones:
            contact_info['phone'] = ''.join(phones[0]) if isinstance(phones[0], tuple) else phones[0]
        
        # LinkedIn pattern
        linkedin_pattern = r'linkedin\.com/in/[\w-]+'
        linkedin = re.findall(linkedin_pattern, text, re.IGNORECASE)
        if linkedin:
            contact_info['linkedin'] = linkedin[0]
        
        return contact_info
    
    def extract_skills(self, text: str) -> List[str]:
        """Extract skills from CV text"""
        # Common skill keywords
        skill_keywords = [
            'python', 'javascript', 'java', 'c++', 'c#', 'html', 'css', 'react', 'angular', 'vue',
            'node.js', 'express', 'django', 'flask', 'spring', 'sql', 'mysql', 'postgresql',
            'mongodb', 'redis', 'docker', 'kubernetes', 'aws', 'azure', 'gcp', 'git', 'linux',
            'machine learning', 'data science', 'artificial intelligence', 'deep learning',
            'tensorflow', 'pytorch', 'scikit-learn', 'pandas', 'numpy', 'matplotlib',
            'project management', 'agile', 'scrum', 'leadership', 'communication', 'teamwork',
            'problem solving', 'analytical', 'creative', 'detail oriented', 'time management'
        ]
        
        text_lower = text.lower()
        found_skills = []
        
        for skill in skill_keywords:
            if skill.lower() in text_lower:
                found_skills.append(skill.title())
        
        return list(set(found_skills))[:20]  # Limit to 20 skills
    
    def extract_education(self, text: str) -> List[str]:
        """Extract education information from CV text"""
        education = []
        
        # Education keywords
        education_keywords = [
            'bachelor', 'master', 'phd', 'doctorate', 'degree', 'university', 'college',
            'school', 'institute', 'academy', 'certification', 'certificate', 'diploma',
            'b.s.', 'b.a.', 'm.s.', 'm.a.', 'mba', 'ph.d.'
        ]
        
        lines = text.split('\n')
        for line in lines:
            line_lower = line.lower()
            if any(keyword in line_lower for keyword in education_keywords):
                if len(line.strip()) > 10:  # Filter out very short lines
                    education.append(line.strip())
        
        return education[:5]  # Limit to 5 education entries
    
    def extract_experience(self, text: str) -> List[str]:
        """Extract work experience from CV text"""
        experience = []
        
        # Experience keywords
        experience_keywords = [
            'experience', 'work', 'employment', 'position', 'role', 'job',
            'company', 'corporation', 'inc', 'ltd', 'llc', 'manager', 'developer',
            'engineer', 'analyst', 'consultant', 'specialist', 'coordinator',
            'director', 'senior', 'junior', 'lead', 'team lead'
        ]
        
        lines = text.split('\n')
        for line in lines:
            line_lower = line.lower()
            if any(keyword in line_lower for keyword in experience_keywords):
                if len(line.strip()) > 15:  # Filter out very short lines
                    experience.append(line.strip())
        
        return experience[:10]  # Limit to 10 experience entries
    
    def parse_cv(self, filename: str, file_content: bytes) -> Dict:
        """Main method to parse CV and extract all information"""
        try:
            # Extract text based on file type
            if filename.lower().endswith('.pdf'):
                text = self.parse_pdf(file_content)
            elif filename.lower().endswith('.docx'):
                text = self.parse_docx(file_content)
            elif filename.lower().endswith('.txt'):
                text = file_content.decode('utf-8')
            else:
                raise ValueError(f"Unsupported file type: {filename}")
            
            if not text.strip():
                raise ValueError("No text could be extracted from the file")
            
            # Extract information
            contact_info = self.extract_contact_info(text)
            skills = self.extract_skills(text)
            education = self.extract_education(text)
            experience = self.extract_experience(text)
            
            return {
                'filename': filename,
                'content': text,
                'skills': skills,
                'education': education,
                'experience': experience,
                'contact_info': contact_info,
                'parsed_at': datetime.now()
            }
            
        except Exception as e:
            logger.error(f"Error parsing CV {filename}: {e}")
            raise

