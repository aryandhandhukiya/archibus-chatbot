import json
import os
from typing import List, Dict, Any
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer

class TicketDataProcessor:
    def __init__(self):
        self.vectorizer = TfidfVectorizer(
            max_features=1000,
            stop_words='english',
            ngram_range=(1, 2)  # Added for better matching
        )
        self.tickets_data = []
        self.embeddings = None
        
    def load_tickets(self, api_output_dir: str):
        """Load all ticket data from JSON files"""
        texts = []
        for filename in os.listdir(api_output_dir):
            if filename.endswith('.json'):
                with open(os.path.join(api_output_dir, filename), 'r', encoding='utf-8') as f:
                    ticket_data = json.load(f)
                    processed_ticket = {
                        'ticket_id': ticket_data['ticket_number'],
                        'title': ticket_data['title'],
                        'description': ticket_data['description'],
                        'status': ticket_data['status'],
                        'solution': self._extract_solution(ticket_data['comments']),
                        'attachments': ticket_data['attachments']
                    }
                    self.tickets_data.append(processed_ticket)
                    # Include title, description and solution in the text for better matching
                    texts.append(f"{ticket_data['title']} {ticket_data['description']} {processed_ticket['solution']}")
        
        if texts:
            self.embeddings = self.vectorizer.fit_transform(texts)
    
    def _extract_solution(self, comments: List[Dict]) -> str:
        """Extract the solution from ticket comments"""
        agent_comments = [c['body'] for c in comments 
                         if not c.get('public', True)]
        return agent_comments[-1] if agent_comments else ""
    
    def find_similar_tickets(self, query: str, top_k: int = 3) -> List[Dict]:
        """Find similar tickets based on query"""
        if not self.embeddings or not self.tickets_data:
            return []
            
        query_vector = self.vectorizer.transform([query])
        similarities = (self.embeddings * query_vector.T).toarray().flatten()
        top_indices = np.argsort(similarities)[-top_k:][::-1]
        
        return [self.tickets_data[i] for i in top_indices]