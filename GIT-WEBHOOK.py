import os
import hmac
import hashlib
import logging
from datetime import datetime
from flask import Flask, request, jsonify
import requests
from requests.exceptions import RequestException, Timeout

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('webhook.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Configuration with environment variables for security
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "")
CHAT_ID = os.getenv("CHAT_ID", "")
GITHUB_WEBHOOK_SECRET = os.getenv("GITHUB_WEBHOOK_SECRET")  # Optional webhook secret
MAX_MESSAGE_LENGTH = 4096  # Telegram message limit

class TelegramBot:
    def __init__(self, token, chat_id):
        self.token = token
        self.chat_id = chat_id
        self.base_url = f"https://api.telegram.org/bot{token}"
    
    def send_message(self, text, parse_mode="Markdown", disable_web_page_preview=True):
        """Send message to Telegram with error handling and message length management"""
        try:
            # Split long messages
            if len(text) > MAX_MESSAGE_LENGTH:
                messages = self._split_message(text)
                for msg in messages:
                    self._send_single_message(msg, parse_mode, disable_web_page_preview)
            else:
                self._send_single_message(text, parse_mode, disable_web_page_preview)
        except Exception as e:
            logger.error(f"Failed to send Telegram message: {e}")
    
    def _send_single_message(self, text, parse_mode, disable_web_page_preview):
        """Send a single message to Telegram"""
        url = f"{self.base_url}/sendMessage"
        payload = {
            "chat_id": self.chat_id,
            "text": text,
            "parse_mode": parse_mode,
            "disable_web_page_preview": disable_web_page_preview
        }
        
        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()
        logger.info(f"Message sent successfully to chat {self.chat_id}")
    
    def _split_message(self, text):
        """Split long messages into chunks"""
        messages = []
        while len(text) > MAX_MESSAGE_LENGTH:
            split_index = text.rfind('\n', 0, MAX_MESSAGE_LENGTH)
            if split_index == -1:
                split_index = MAX_MESSAGE_LENGTH
            messages.append(text[:split_index])
            text = text[split_index:].lstrip()
        if text:
            messages.append(text)
        return messages

# Initialize Telegram bot
telegram_bot = TelegramBot(TELEGRAM_TOKEN, CHAT_ID)

def verify_github_signature(payload_body, signature_header):
    """Verify GitHub webhook signature for security"""
    if not GITHUB_WEBHOOK_SECRET or not signature_header:
        return True  # Skip verification if no secret is configured
    
    try:
        hash_object = hmac.new(
            GITHUB_WEBHOOK_SECRET.encode('utf-8'),
            msg=payload_body,
            digestmod=hashlib.sha256
        )
        expected_signature = "sha256=" + hash_object.hexdigest()
        return hmac.compare_digest(expected_signature, signature_header)
    except Exception as e:
        logger.error(f"Signature verification error: {e}")
        return False

def format_commit_info(commits):
    """Format commit information for display"""
    if not commits:
        return ""
    
    commit_info = []
    for commit in commits[:5]:  # Limit to 5 commits
        author = commit.get('author', {}).get('name', 'Unknown')
        message = commit.get('message', '').split('\n')[0][:100]  # First line, max 100 chars
        commit_id = commit.get('id', '')[:7]  # Short commit hash
        commit_info.append(f"• `{commit_id}` {message} - {author}")
    
    if len(commits) > 5:
        commit_info.append(f"... and {len(commits) - 5} more commits")
    
    return '\n'.join(commit_info)

def handle_push_event(payload):
    """Handle GitHub push events"""
    repo = payload.get("repository", {}).get("full_name", "Unknown")
    pusher = payload.get("pusher", {}).get("name", "Unknown")
    ref = payload.get("ref", "").replace("refs/heads/", "")
    commits = payload.get("commits", [])
    compare_url = payload.get("compare", "")
    
    commit_count = len(commits)
    commit_word = "commit" if commit_count == 1 else "commits"
    
    message = f"🚀 *Push to {repo}*\n"
    message += f"📝 {commit_count} {commit_word} by `{pusher}` to `{ref}`\n\n"
    
    if commits:
        message += "*Commits:*\n"
        message += format_commit_info(commits)
        message += f"\n\n[View Changes]({compare_url})"
    
    telegram_bot.send_message(message)

def handle_issues_event(payload):
    """Handle GitHub issues events"""
    action = payload.get("action", "unknown")
    issue = payload.get("issue", {})
    issue_title = issue.get("title", "Unknown")
    issue_number = issue.get("number", "")
    issue_url = issue.get("html_url", "")
    repo = payload.get("repository", {}).get("full_name", "Unknown")
    user = payload.get("sender", {}).get("login", "Unknown")
    
    emoji_map = {
        "opened": "🐛",
        "closed": "✅",
        "reopened": "🔄",
        "assigned": "👤",
        "unassigned": "👤",
        "labeled": "🏷️",
        "unlabeled": "🏷️"
    }
    
    emoji = emoji_map.get(action, "📋")
    
    message = f"{emoji} *Issue {action}* in {repo}\n"
    message += f"#{issue_number}: [{issue_title}]({issue_url})\n"
    message += f"by `{user}`"
    
    telegram_bot.send_message(message)

def handle_pull_request_event(payload):
    """Handle GitHub pull request events"""
    action = payload.get("action", "unknown")
    pr = payload.get("pull_request", {})
    pr_title = pr.get("title", "Unknown")
    pr_number = pr.get("number", "")
    pr_url = pr.get("html_url", "")
    repo = payload.get("repository", {}).get("full_name", "Unknown")
    user = payload.get("sender", {}).get("login", "Unknown")
    
    emoji_map = {
        "opened": "🔀",
        "closed": "✅" if pr.get("merged") else "❌",
        "reopened": "🔄",
        "merged": "🎉",
        "ready_for_review": "👀",
        "review_requested": "👀"
    }
    
    emoji = emoji_map.get(action, "🔀")
    
    message = f"{emoji} *PR {action}* in {repo}\n"
    message += f"#{pr_number}: [{pr_title}]({pr_url})\n"
    message += f"by `{user}`"
    
    # Add merge info if PR was merged
    if action == "closed" and pr.get("merged"):
        message = message.replace("closed", "merged")
        message = message.replace("❌", "🎉")
    
    telegram_bot.send_message(message)

def handle_release_event(payload):
    """Handle GitHub release events"""
    action = payload.get("action", "unknown")
    release = payload.get("release", {})
    tag_name = release.get("tag_name", "Unknown")
    name = release.get("name", tag_name)
    html_url = release.get("html_url", "")
    repo = payload.get("repository", {}).get("full_name", "Unknown")
    
    if action == "published":
        message = f"🎉 *New Release* in {repo}\n"
        message += f"📦 [{name}]({html_url})\n"
        message += f"Tag: `{tag_name}`"
        telegram_bot.send_message(message)

def handle_star_event(payload):
    """Handle GitHub star events"""
    action = payload.get("action", "unknown")
    repo = payload.get("repository", {}).get("full_name", "Unknown")
    user = payload.get("sender", {}).get("login", "Unknown")
    stars = payload.get("repository", {}).get("stargazers_count", 0)
    
    if action == "created":
        message = f"⭐ *New Star* for {repo}\n"
        message += f"Starred by `{user}`\n"
        message += f"Total stars: {stars}"
        telegram_bot.send_message(message)

@app.route("/health", methods=["GET"])
def health_check():
    """Health check endpoint"""
    return jsonify({"status": "healthy", "timestamp": datetime.now().isoformat()})

@app.route("/github-webhook", methods=["POST"])
def github_webhook():
    """Main webhook endpoint"""
    try:
        # Get headers
        event = request.headers.get("X-GitHub-Event")
        signature = request.headers.get("X-Hub-Signature-256")
        delivery = request.headers.get("X-GitHub-Delivery")
        
        # Get payload
        payload_body = request.get_data()
        
        # Verify signature if secret is configured
        if not verify_github_signature(payload_body, signature):
            logger.warning(f"Invalid signature for delivery {delivery}")
            return jsonify({"error": "Invalid signature"}), 401
        
        # Parse JSON payload
        try:
            payload = request.get_json(force=True)
        except Exception as e:
            logger.error(f"Invalid JSON payload: {e}")
            return jsonify({"error": "Invalid JSON"}), 400
        
        logger.info(f"Received {event} event (delivery: {delivery})")
        
        # Handle different event types
        if event == "push":
            handle_push_event(payload)
        elif event == "issues":
            handle_issues_event(payload)
        elif event == "pull_request":
            handle_pull_request_event(payload)
        elif event == "release":
            handle_release_event(payload)
        elif event == "star":
            handle_star_event(payload)
        else:
            logger.info(f"Unhandled event type: {event}")
        
        return jsonify({"status": "success"}), 200
        
    except RequestException as e:
        logger.error(f"Network error: {e}")
        return jsonify({"error": "Network error"}), 500
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return jsonify({"error": "Internal server error"}), 500

@app.errorhandler(404)
def not_found(error):
    return jsonify({"error": "Not found"}), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({"error": "Internal server error"}), 500

if __name__ == "__main__":
    # Validate configuration
    if not TELEGRAM_TOKEN or not CHAT_ID:
        logger.error("TELEGRAM_TOKEN and CHAT_ID must be configured")
        exit(1)
    
    logger.info("Starting GitHub webhook server...")
    
    # Run with better configuration for production
    port = int(os.getenv("PORT", 5000))
    debug = os.getenv("FLASK_ENV") == "development"
    
    app.run(
        host="0.0.0.0",
        port=port,
        debug=debug,
        threaded=True
    )
