import os, re, urllib.parse, urllib.request
from flask import Flask, abort, jsonify, render_template, request

app = Flask(__name__)

# Contact database - stores contact names and phone numbers
CONTACTS = {
    "mom": "+919441651317",
    "dad": "+919550654590",
    "alice": "+1-555-0103",
    "bob": "+1-555-0104",
    "emergency": "911",
    "police": "911",
    "ambulance": "911",
}

def get_vid(q):
    try:
        req = urllib.request.Request(f"https://www.youtube.com/results?search_query={urllib.parse.quote(q)}", headers={"User-Agent": "Mozilla/5.0"})
        ids = re.findall(r"\"videoId\":\"([^\"]+)\"", urllib.request.urlopen(req, timeout=5).read().decode("utf-8"))
        return ids[0] if ids else None
    except Exception: return None

def parse_phone_number(text):
    """Extract and format phone number from text"""
    # Remove common words
    phone_text = text.lower()
    for p in ["call", "phone", "number", "to", "dial", "call me"]:
        phone_text = phone_text.replace(p, "")
    
    # Check if it's a contact name
    for contact_name, phone in CONTACTS.items():
        if contact_name in phone_text:
            return phone
    
    # Try to extract digits and convert spelled-out numbers
    phone_text = re.sub(r'[^\d\s\-\+]', '', phone_text)
    digits = re.findall(r'[\d\-\+]+', phone_text)
    
    if digits:
        phone = ''.join(digits)
        # Remove extra formatting
        phone = re.sub(r'[\-\+]+', '', phone)
        # Validate phone number length (10-15 digits typically)
        if 10 <= len(phone) <= 15:
            return phone
    return None

@app.route("/", methods=["GET"])
def home(): return render_template("index.html")

@app.route("/contacts", methods=["GET"])
def get_contacts(): 
    """Return list of available contacts"""
    return jsonify({"contacts": list(CONTACTS.keys())})

@app.route("/contacts", methods=["POST"])
def add_contact():
    """Add or update a contact"""
    d = request.get_json(silent=True)
    if not d or "name" not in d or "phone" not in d: 
        abort(400, description="Missing 'name' or 'phone' in request body")
    
    name = d["name"].strip().lower()
    phone = d["phone"].strip()
    
    if not re.match(r'^[\d\-\+\s]+$', phone):
        abort(400, description="Invalid phone number format")
    
    CONTACTS[name] = phone
    return jsonify({"status": "success", "message": f"Contact '{name}' added/updated"})

@app.route("/agent", methods=["POST"])
def ai_agent_router():
    d = request.get_json(silent=True)
    if not d or "text_command" not in d: abort(400, description="Missing 'text_command' in request body")
    
    cmd = d["text_command"].strip().lower()

    if any(k in cmd for k in ["call", "phone", "dial"]):
        phone = parse_phone_number(cmd)
        if phone:
            # Format phone number for tel: URI
            phone_formatted = re.sub(r'[^\d\+]', '', phone)
            target = f"tel:{phone_formatted}"
            return jsonify({"action": "call", "url": target, "phone": phone})
        else:
            return jsonify({"action": "error", "message": "Could not parse phone number or contact name from command"})

    elif "youtube" in cmd:
        q = cmd
        for p in ["open youtube and search", "open youtube and play", "open youtube", "search for", "search", "and play", "play", "on youtube"]:
            q = q.replace(p, "")
        q = q.strip()
        vid = get_vid(q)
        target = "https://www.youtube.com" if not q else (f"https://www.youtube.com/watch?v={vid}&autoplay=1" if vid else f"https://www.youtube.com/results?search_query={urllib.parse.quote_plus(q)}")

    elif any(k in cmd for k in ["gmail", "email", "mail", "message"]):
        to, body = "", ""
        if tm := re.search(r"(?:update|send|mail|message)?\s*to\s+([a-zA-Z0-9._%+\s]+?)(?=\s+(?:and|type|write|saying|with|content|that|message|$))", cmd):
            c = tm.group(1).strip().replace(" at ", "@").replace(" dot ", ".").replace(" ", "")
            to = c if "@" in c else f"{c}@gmail.com"

        if bm := re.search(r"(?:type|write|saying|content|message|that)\s+(.*)", cmd):
            if b := bm.group(1).strip(): body = b[0].upper() + b[1:]

        target = f"https://mail.google.com/mail/u/0/?view=cm&fs=1&to={urllib.parse.quote(to)}&body={urllib.parse.quote(body)}" if to or body else "https://mail.google.com"

    else:
        target = f"https://www.google.com/search?q={urllib.parse.quote_plus(cmd)}"

    return jsonify({"action": "open_tab", "url": target})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
