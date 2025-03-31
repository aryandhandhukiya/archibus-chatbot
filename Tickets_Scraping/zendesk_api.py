import requests
from datetime import datetime
import os
import json
from typing import Optional, Dict, Any

class ZendeskAPI:
    def __init__(self):
        self.domain = "isquaredhelp.zendesk.com"
        self.email = "harsh_khanna@isquared.co.jp"
        self.api_token = "lFTBdRNSPQRImJbG5QwhkmyhQAr88rQO5IOH0TkA"
        self.base_url = f"https://{self.domain}/api/v2"
        self.session = requests.Session()
        self.session.auth = (f"{self.email}/token", self.api_token)

    def get_ticket(self, ticket_id: str) -> Optional[Dict[str, Any]]:
        """Fetch a single ticket with its comments and attachments."""
        try:
            # Get ticket details
            ticket_url = f"{self.base_url}/tickets/{ticket_id}"
            ticket_response = self.session.get(ticket_url)
            ticket_response.raise_for_status()
            ticket_data = ticket_response.json()['ticket']

            # Get comments for the ticket
            comments_url = f"{self.base_url}/tickets/{ticket_id}/comments"
            comments_response = self.session.get(comments_url)
            comments_response.raise_for_status()
            comments_data = comments_response.json()['comments']

            # Process attachments
            attachments = []
            for comment in comments_data:
                if comment.get('attachments'):  
                    for attachment in comment['attachments']:
                        attachments.append({
                            'filename': attachment['file_name'],
                            'content_url': attachment['content_url'],
                            'content_type': attachment['content_type']
                        })

            return {
                'ticket_number': ticket_id,
                'url': f"https://{self.domain}/agent/tickets/{ticket_id}",
                'title': ticket_data['subject'],
                'status': ticket_data['status'],
                'requester_id': ticket_data['requester_id'],
                'description': ticket_data['description'],
                'comments': comments_data,
                'attachments': attachments,
                'created_at': ticket_data['created_at'],
                'updated_at': ticket_data['updated_at']
            }

        except requests.exceptions.RequestException as e:
            print(f"Error fetching ticket {ticket_id}: {str(e)}")
            return None

    def download_attachment(self, url: str, filename: str, output_dir: str) -> bool:
        """Download an attachment from a ticket."""
        try:
            response = self.session.get(url)
            response.raise_for_status()
            
            filepath = os.path.join(output_dir, filename)
            with open(filepath, 'wb') as f:
                f.write(response.content)
            return True
        except Exception as e:
            print(f"Error downloading attachment {filename}: {str(e)}")
            return False

def save_ticket_data(data: Dict[str, Any], output_dir: str):
    """Save ticket data and its attachments."""
    if not data:
        return

    # Create directories
    attachments_dir = os.path.join(output_dir, 'attachments', str(data['ticket_number']))
    os.makedirs(attachments_dir, exist_ok=True)

    # Save ticket data as JSON
    json_file = os.path.join(output_dir, f"ticket_{data['ticket_number']}.json")
    with open(json_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    # Save attachments
    zendesk = ZendeskAPI()
    for attachment in data['attachments']:
        zendesk.download_attachment(
            attachment['content_url'],
            attachment['filename'],
            attachments_dir
        )

def main():
    # Setup output directory
    output_dir = os.path.join(os.path.dirname(__file__), 'api_output')
    os.makedirs(output_dir, exist_ok=True)

    zendesk = ZendeskAPI()
    
    # Fetch tickets from 88 to 790
    for ticket_num in range(88, 791):
        formatted_num = f"{ticket_num:03d}"
        print(f"Fetching ticket {formatted_num}...")
        
        ticket_data = zendesk.get_ticket(formatted_num)
        if ticket_data:
            save_ticket_data(ticket_data, output_dir)

if __name__ == "__main__":
    main()