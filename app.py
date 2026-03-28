from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash, send_file
import sqlite3, os, hashlib, io
from datetime import datetime, timedelta
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, HRFlowable
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT

app = Flask(__name__)
app.secret_key = "cardealership_secret_2024"
DB_PATH = "dealership.db"

CAR_IMAGES = {
    "Maruti Swift":    "swift.jpg",
    "Honda City":      "city.jpg",
    "Hyundai Creta":   "creta.jpg",
    "Tata Nexon":      "nexon.jpg",
    "Mahindra Scorpio":"scorpio.jpg",
    "Toyota Innova":   "innova.jpg",
}

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def _seed_cars(c):
    now = datetime.now()
    cars = [
        ("Maruti Swift","Maruti",2021,"Petrol",32000,480000,"Ahmedabad","swift.jpg",
         (now+timedelta(minutes=5)).strftime('%Y-%m-%d %H:%M:%S'),0,'available',
         'Pearl White','Manual','1197cc K-Series',1,'21 kmpl','GJ-01-AB-1234'),
        ("Honda City","Honda",2020,"Petrol",45000,750000,"Surat","city.jpg",
         (now+timedelta(minutes=10)).strftime('%Y-%m-%d %H:%M:%S'),0,'available',
         'Lunar Silver','Manual','1498cc i-VTEC',2,'17 kmpl','GJ-05-CD-5678'),
        ("Hyundai Creta","Hyundai",2022,"Diesel",28000,1100000,"Mumbai","creta.jpg",
         (now+timedelta(minutes=15)).strftime('%Y-%m-%d %H:%M:%S'),0,'available',
         'Typhoon Silver','Automatic','1493cc CRDi',1,'18 kmpl','MH-01-EF-9012'),
        ("Tata Nexon","Tata",2021,"Petrol",38000,850000,"Pune","nexon.jpg",
         (now+timedelta(minutes=20)).strftime('%Y-%m-%d %H:%M:%S'),0,'available',
         'Calgary White','Manual','1199cc Revotron',1,'17 kmpl','MH-12-GH-3456'),
        ("Mahindra Scorpio","Mahindra",2019,"Diesel",65000,950000,"Jaipur","scorpio.jpg",
         (now+timedelta(minutes=25)).strftime('%Y-%m-%d %H:%M:%S'),0,'available',
         'Napoli Black','Manual','2179cc mHawk',2,'15 kmpl','RJ-14-IJ-7890'),
        ("Toyota Innova","Toyota",2020,"Diesel",55000,1350000,"Delhi","innova.jpg",
         (now+timedelta(minutes=30)).strftime('%Y-%m-%d %H:%M:%S'),0,'available',
         'Super White','Automatic','2755cc 2GD-FTV',2,'14 kmpl','DL-01-KL-2345'),
    ]
    c.executemany("""INSERT INTO cars
        (name,brand,year,fuel,km,price,city,image,auction_end,highest_bid,status,
         color,transmission,engine,owners,mileage,registration)
        VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", cars)

def _reset_auction_timers(c):
    now = datetime.now()
    c.execute("SELECT id FROM cars ORDER BY id")
    cars = c.fetchall()
    for i, car in enumerate(cars):
        new_end = (now + timedelta(minutes=5*(i+1))).strftime('%Y-%m-%d %H:%M:%S')
        c.execute("UPDATE cars SET status='available', auction_end=?, highest_bid=0 WHERE id=?",
                  (new_end, car['id']))
    c.execute("DELETE FROM bids")

def init_db():
    conn = get_db(); c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS dealers (
        id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL, mobile TEXT NOT NULL, password TEXT NOT NULL,
        business_name TEXT, city TEXT, pan TEXT, aadhaar TEXT,
        account_no TEXT, ifsc TEXT, status TEXT DEFAULT 'incomplete',
        is_admin INTEGER DEFAULT 0, created_at TEXT DEFAULT (datetime('now')))""")
    try: c.execute("ALTER TABLE dealers ADD COLUMN is_admin INTEGER DEFAULT 0")
    except: pass
    c.execute("""CREATE TABLE IF NOT EXISTS cars (
        id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, brand TEXT NOT NULL,
        year INTEGER, fuel TEXT, km INTEGER, price REAL, city TEXT, image TEXT,
        auction_end TEXT, highest_bid REAL DEFAULT 0, status TEXT DEFAULT 'available',
        color TEXT DEFAULT 'White', transmission TEXT DEFAULT 'Manual',
        engine TEXT DEFAULT '1200cc', owners INTEGER DEFAULT 1,
        mileage TEXT DEFAULT '18 kmpl', registration TEXT DEFAULT 'GJ-01')""")
    for col, defval in [("color","'White'"),("transmission","'Manual'"),("engine","'1200cc'"),
                        ("owners","1"),("mileage","'18 kmpl'"),("registration","'GJ-01'")]:
        try: c.execute(f"ALTER TABLE cars ADD COLUMN {col} TEXT DEFAULT {defval}")
        except: pass
    c.execute("""CREATE TABLE IF NOT EXISTS bids (
        id INTEGER PRIMARY KEY AUTOINCREMENT, dealer_id INTEGER, car_id INTEGER,
        bid_amount REAL, bid_time TEXT DEFAULT (datetime('now')),
        FOREIGN KEY(dealer_id) REFERENCES dealers(id), FOREIGN KEY(car_id) REFERENCES cars(id))""")
    c.execute("""CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT, dealer_id INTEGER, car_id INTEGER,
        price REAL, loan_amount REAL DEFAULT 0, emi_amount REAL DEFAULT 0,
        tenure_months INTEGER DEFAULT 0, status TEXT DEFAULT 'pending',
        purchase_type TEXT DEFAULT 'auction', created_at TEXT DEFAULT (datetime('now')),
        FOREIGN KEY(dealer_id) REFERENCES dealers(id), FOREIGN KEY(car_id) REFERENCES cars(id))""")
    for col, defval in [("loan_amount","0"),("emi_amount","0"),("tenure_months","0"),("purchase_type","'auction'")]:
        try: c.execute(f"ALTER TABLE orders ADD COLUMN {col} REAL DEFAULT {defval}")
        except: pass
    c.execute("""CREATE TABLE IF NOT EXISTS documents (
        id INTEGER PRIMARY KEY AUTOINCREMENT, dealer_id INTEGER, car_id INTEGER,
        doc_type TEXT, filename TEXT, status TEXT DEFAULT 'pending',
        uploaded_at TEXT DEFAULT (datetime('now')),
        FOREIGN KEY(dealer_id) REFERENCES dealers(id), FOREIGN KEY(car_id) REFERENCES cars(id))""")
    c.execute("""CREATE TABLE IF NOT EXISTS notifications (
        id INTEGER PRIMARY KEY AUTOINCREMENT, dealer_id INTEGER, message TEXT,
        type TEXT DEFAULT 'info', is_read INTEGER DEFAULT 0,
        created_at TEXT DEFAULT (datetime('now')),
        FOREIGN KEY(dealer_id) REFERENCES dealers(id))""")
    c.execute("SELECT COUNT(*) FROM cars")
    if c.fetchone()[0] == 0:
        _seed_cars(c)
    else:
        c.execute("SELECT COUNT(*) FROM cars WHERE status='available' AND auction_end > datetime('now')")
        if c.fetchone()[0] == 0:
            _reset_auction_timers(c)
    conn.commit(); conn.close()

def resolve_ended_auctions():
    conn = get_db(); c = conn.cursor()
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    expired = c.execute(
        "SELECT * FROM cars WHERE status='available' AND auction_end <= ?", (now,)
    ).fetchall()
    for car in expired:
        top_bid = c.execute(
            """SELECT b.*, d.name as dealer_name FROM bids b
               JOIN dealers d ON b.dealer_id=d.id
               WHERE b.car_id=? ORDER BY b.bid_amount DESC LIMIT 1""",
            (car['id'],)
        ).fetchone()
        if top_bid:
            winner_id = top_bid['dealer_id']
            win_amount = top_bid['bid_amount']
            existing = c.execute(
                "SELECT id FROM orders WHERE car_id=? AND purchase_type='auction'", (car['id'],)
            ).fetchone()
            if not existing:
                c.execute(
                    """INSERT INTO orders(dealer_id,car_id,price,loan_amount,emi_amount,
                       tenure_months,status,purchase_type) VALUES(?,?,?,0,0,0,'confirmed','auction')""",
                    (winner_id, car['id'], win_amount)
                )
                c.execute(
                    "INSERT INTO notifications(dealer_id,message,type) VALUES(?,?,?)",
                    (winner_id,
                     f"Congratulations! You won the auction for {car['name']} {car['year']} "
                     f"at Rs.{win_amount:,.0f}. Check My Orders.",
                     'win')
                )
                others = c.execute(
                    "SELECT DISTINCT dealer_id FROM bids WHERE car_id=? AND dealer_id!=?",
                    (car['id'], winner_id)
                ).fetchall()
                for b in others:
                    c.execute(
                        "INSERT INTO notifications(dealer_id,message,type) VALUES(?,?,?)",
                        (b['dealer_id'],
                         f"Auction ended for {car['name']} {car['year']}. "
                         f"Winning bid: Rs.{win_amount:,.0f}. Better luck next time!",
                         'info')
                    )
        c.execute("UPDATE cars SET status='sold' WHERE id=?", (car['id'],))
    conn.commit(); conn.close()

def hash_pw(pw): return hashlib.sha256(pw.encode()).hexdigest()

def login_required(f):
    from functools import wraps
    @wraps(f)
    def dec(*args, **kwargs):
        if "dealer_id" not in session: return redirect(url_for("login"))
        return f(*args, **kwargs)
    return dec

@app.route("/")
def index(): return render_template("index.html")

@app.route("/signup", methods=["GET","POST"])
def signup():
    if request.method == "POST":
        name=request.form.get("name","").strip(); mobile=request.form.get("mobile","").strip()
        email=request.form.get("email","").strip(); biz=request.form.get("business_name","").strip()
        city=request.form.get("city","").strip(); pw=request.form.get("password","").strip()
        if not all([name,mobile,email,biz,city,pw]):
            flash("All fields are required.","error"); return render_template("signup.html")
        conn=get_db()
        try:
            conn.execute("INSERT INTO dealers(name,mobile,email,business_name,city,password,status) VALUES(?,?,?,?,?,?,?)",
                         (name,mobile,email,biz,city,hash_pw(pw),"incomplete"))
            conn.commit()
            d=conn.execute("SELECT * FROM dealers WHERE email=?",(email,)).fetchone()
            session["dealer_id"]=d["id"]; session["dealer_name"]=d["name"]
            return redirect(url_for("onboarding"))
        except sqlite3.IntegrityError:
            flash("Email already registered.","error"); return render_template("signup.html")
        finally: conn.close()
    return render_template("signup.html")

@app.route("/login", methods=["GET","POST"])
def login():
    if request.method == "POST":
        email=request.form.get("email","").strip(); pw=request.form.get("password","").strip()
        conn=get_db()
        d=conn.execute("SELECT * FROM dealers WHERE email=? AND password=?",(email,hash_pw(pw))).fetchone()
        conn.close()
        if d:
            session["dealer_id"]=d["id"]; session["dealer_name"]=d["name"]
            if d["status"]=="incomplete": return redirect(url_for("onboarding"))
            return redirect(url_for("dashboard"))
        flash("Invalid credentials.","error")
    return render_template("login.html")

@app.route("/logout")
def logout(): session.clear(); return redirect(url_for("index"))

@app.route("/onboarding", methods=["GET","POST"])
@login_required
def onboarding():
    step=int(request.args.get("step",1)); did=session["dealer_id"]
    if request.method=="POST":
        conn=get_db()
        if step==1:
            conn.execute("UPDATE dealers SET business_name=?,city=? WHERE id=?",
                         (request.form.get("business_name"),request.form.get("city"),did))
            conn.commit(); conn.close(); return redirect(url_for("onboarding",step=2))
        elif step==2:
            conn.execute("UPDATE dealers SET pan=?,aadhaar=? WHERE id=?",
                         (request.form.get("pan"),request.form.get("aadhaar"),did))
            conn.commit(); conn.close(); return redirect(url_for("onboarding",step=3))
        elif step==3:
            conn.execute("UPDATE dealers SET account_no=?,ifsc=?,status='pending' WHERE id=?",
                         (request.form.get("account_no"),request.form.get("ifsc"),did))
            conn.commit(); conn.close(); return redirect(url_for("onboarding",step=4))
    conn=get_db(); dealer=conn.execute("SELECT * FROM dealers WHERE id=?",(did,)).fetchone(); conn.close()
    return render_template("onboarding.html",step=step,dealer=dealer)

@app.route("/onboarding/skip")
@login_required
def skip_onboarding():
    conn=get_db()
    conn.execute("UPDATE dealers SET status='pending' WHERE id=?",(session["dealer_id"],))
    conn.commit(); conn.close()
    return redirect(url_for("dashboard"))

@app.route("/dashboard")
@login_required
def dashboard():
    resolve_ended_auctions()
    did=session["dealer_id"]; conn=get_db()
    dealer=conn.execute("SELECT * FROM dealers WHERE id=?",(did,)).fetchone()
    cars=conn.execute("SELECT * FROM cars WHERE status='available' ORDER BY auction_end ASC").fetchall()
    my_bids=conn.execute("""SELECT b.*,c.name as car_name,c.brand,c.year,c.highest_bid,c.id as car_id,c.price
        FROM bids b JOIN cars c ON b.car_id=c.id WHERE b.dealer_id=? ORDER BY b.bid_time DESC""",(did,)).fetchall()
    my_orders=conn.execute("""SELECT o.*,c.name as car_name,c.brand,c.year,c.color,c.fuel,c.km,c.registration
        FROM orders o JOIN cars c ON o.car_id=c.id WHERE o.dealer_id=? ORDER BY o.created_at DESC""",(did,)).fetchall()
    conn.close()
    cars_with_images = []
    for car in cars:
        d = dict(car)
        d['img_url'] = CAR_IMAGES.get(car['name'], '')
        cars_with_images.append(d)
    
    # Get theme from session or default to light
    theme = session.get("theme", "light")
    
    return render_template("dashboard.html",dealer=dealer,cars=cars_with_images,
                           my_bids=my_bids,my_orders=my_orders, theme=theme)

@app.route("/api/set-theme", methods=["POST"])
@login_required
def set_theme():
    data = request.get_json()
    theme = data.get("theme", "light")
    session["theme"] = theme
    return jsonify({"success": True, "theme": theme})

@app.route("/api/bid", methods=["POST"])
@login_required
def place_bid():
    resolve_ended_auctions()
    data=request.get_json(); did=session["dealer_id"]
    car_id=data.get("car_id"); amount=float(data.get("bid_amount",0))
    conn=get_db()
    car=conn.execute("SELECT * FROM cars WHERE id=? AND status='available'",(car_id,)).fetchone()
    if not car:
        conn.close(); return jsonify({"success":False,"message":"Auction has ended or car not found."})
    now = datetime.now()
    auction_end = datetime.strptime(car['auction_end'], '%Y-%m-%d %H:%M:%S')
    if now > auction_end:
        conn.close(); resolve_ended_auctions()
        return jsonify({"success":False,"message":"This auction has already ended."})
    if amount <= car["highest_bid"]:
        conn.close()
        return jsonify({"success":False,"message":f"Bid must exceed Rs.{car['highest_bid']:,.0f}"})
    prev_top = conn.execute(
        "SELECT dealer_id FROM bids WHERE car_id=? ORDER BY bid_amount DESC LIMIT 1",(car_id,)
    ).fetchone()
    conn.execute("INSERT INTO bids(dealer_id,car_id,bid_amount) VALUES(?,?,?)",(did,car_id,amount))
    conn.execute("UPDATE cars SET highest_bid=? WHERE id=?",(amount,car_id))
    if prev_top and prev_top['dealer_id'] != did:
        conn.execute(
            "INSERT INTO notifications(dealer_id,message,type) VALUES(?,?,?)",
            (prev_top['dealer_id'],
             f"You have been outbid on {car['name']} {car['year']}! "
             f"New highest bid: Rs.{amount:,.0f}. Place a higher bid to stay ahead!",
             'outbid')
        )
    conn.commit(); conn.close()
    return jsonify({"success":True,"message":"Bid placed successfully!","new_highest":amount})

@app.route("/api/live-bids")
@login_required
def live_bids():
    resolve_ended_auctions()
    conn = get_db()
    cars = conn.execute(
        "SELECT * FROM cars WHERE status='available' ORDER BY auction_end ASC"
    ).fetchall()
    result = []
    for car in cars:
        bids = conn.execute(
            """SELECT b.bid_amount, b.bid_time,
                      SUBSTR(d.name,1,1)||REPLACE(SUBSTR(d.name,2,LENGTH(d.name)-2),' ','*')||SUBSTR(d.name,-1,1) as masked_name
               FROM bids b JOIN dealers d ON b.dealer_id=d.id
               WHERE b.car_id=? ORDER BY b.bid_amount DESC LIMIT 10""",
            (car['id'],)
        ).fetchall()
        bid_count = conn.execute(
            "SELECT COUNT(*) as cnt FROM bids WHERE car_id=?", (car['id'],)
        ).fetchone()['cnt']
        result.append({
            'car_id': car['id'],
            'car_name': f"{car['name']} {car['year']}",
            'highest_bid': car['highest_bid'],
            'base_price': car['price'],
            'auction_end': car['auction_end'],
            'status': car['status'],
            'bid_count': bid_count,
            'bids': [{'amount': b['bid_amount'], 'time': b['bid_time'], 'bidder': b['masked_name']} for b in bids]
        })
    conn.close()
    return jsonify({'auctions': result, 'server_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')})

@app.route("/api/notifications")
@login_required
def get_notifications():
    did = session["dealer_id"]; conn = get_db()
    notifs = conn.execute(
        "SELECT * FROM notifications WHERE dealer_id=? ORDER BY created_at DESC LIMIT 20", (did,)
    ).fetchall()
    unread = conn.execute(
        "SELECT COUNT(*) as cnt FROM notifications WHERE dealer_id=? AND is_read=0", (did,)
    ).fetchone()['cnt']
    conn.close()
    return jsonify({'notifications': [dict(n) for n in notifs], 'unread_count': unread})

@app.route("/api/notifications/mark-read", methods=["POST"])
@login_required
def mark_notifications_read():
    did = session["dealer_id"]; conn = get_db()
    conn.execute("UPDATE notifications SET is_read=1 WHERE dealer_id=?", (did,))
    conn.commit(); conn.close()
    return jsonify({'success': True})

@app.route("/api/buy-now", methods=["POST"])
@login_required
def buy_now():
    data=request.get_json(); did=session["dealer_id"]
    car_id=data.get("car_id"); loan_amount=float(data.get("loan_amount",0))
    emi_amount=float(data.get("emi_amount",0)); tenure=int(data.get("tenure_months",0))
    conn=get_db()
    car=conn.execute("SELECT * FROM cars WHERE id=? AND status='available'",(car_id,)).fetchone()
    if not car: conn.close(); return jsonify({"success":False,"message":"Car not available"})
    docs=conn.execute("SELECT doc_type FROM documents WHERE dealer_id=? AND car_id=?",(did,car_id)).fetchall()
    missing = {"aadhaar","pan","address_proof"} - {d["doc_type"] for d in docs}
    if missing:
        conn.close()
        return jsonify({"success":False,"message":"Upload all required documents first","missing_docs":list(missing)})
    price = car["highest_bid"] if car["highest_bid"] > car["price"] else car["price"]
    conn.execute("INSERT INTO orders(dealer_id,car_id,price,loan_amount,emi_amount,tenure_months,status,purchase_type) VALUES(?,?,?,?,?,?,?,?)",
                 (did,car_id,price,loan_amount,emi_amount,tenure,"pending","buy_now"))
    conn.execute("UPDATE cars SET status='sold' WHERE id=?",(car_id,))
    conn.commit(); conn.close()
    return jsonify({"success":True,"message":"Purchase confirmed! Check My Orders."})

@app.route("/api/upload-document", methods=["POST"])
@login_required
def upload_document():
    did=session["dealer_id"]; car_id=request.form.get("car_id"); doc_type=request.form.get("doc_type")
    if not car_id or not doc_type: return jsonify({"success":False,"message":"Missing parameters"})
    conn=get_db()
    existing=conn.execute("SELECT id FROM documents WHERE dealer_id=? AND car_id=? AND doc_type=?",(did,car_id,doc_type)).fetchone()
    if existing:
        conn.execute("UPDATE documents SET status='pending',uploaded_at=datetime('now') WHERE dealer_id=? AND car_id=? AND doc_type=?",(did,car_id,doc_type))
    else:
        conn.execute("INSERT INTO documents(dealer_id,car_id,doc_type,filename,status) VALUES(?,?,?,?,?)",
                     (did,car_id,doc_type,f"{doc_type}_{did}_{car_id}.pdf","pending"))
    conn.commit()
    docs=conn.execute("SELECT doc_type FROM documents WHERE dealer_id=? AND car_id=?",(did,car_id)).fetchall()
    conn.close()
    return jsonify({"success":True,"message":"Document uploaded successfully","uploaded":[d["doc_type"] for d in docs]})

@app.route("/api/check-documents/<int:car_id>")
@login_required
def check_documents(car_id):
    did=session["dealer_id"]; conn=get_db()
    docs=conn.execute("SELECT doc_type FROM documents WHERE dealer_id=? AND car_id=?",(did,car_id)).fetchall()
    conn.close()
    uploaded=[d["doc_type"] for d in docs]; required=["aadhaar","pan","address_proof"]
    return jsonify({"uploaded":uploaded,"required":required,"complete":all(r in uploaded for r in required)})

@app.route("/api/reset-auctions", methods=["POST"])
@login_required
def reset_auctions():
    conn = get_db(); c = conn.cursor()
    _reset_auction_timers(c)
    conn.commit(); conn.close()
    return jsonify({"success":True,"message":"All auctions reset with fresh 5-minute timers."})

@app.route("/inspection-report/<int:car_id>")
@login_required
def inspection_report(car_id):
    conn=get_db(); car=conn.execute("SELECT * FROM cars WHERE id=?",(car_id,)).fetchone(); conn.close()
    if not car: flash("Car not found","error"); return redirect(url_for("dashboard"))
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer,pagesize=A4,rightMargin=2*cm,leftMargin=2*cm,topMargin=2*cm,bottomMargin=2*cm)
    story = []
    title_style  = ParagraphStyle('T',fontSize=22,fontName='Helvetica-Bold',textColor=colors.HexColor('#1a1a2e'),spaceAfter=4,alignment=TA_CENTER)
    sub_style    = ParagraphStyle('S',fontSize=11,fontName='Helvetica',textColor=colors.HexColor('#666666'),spaceAfter=2,alignment=TA_CENTER)
    section_style= ParagraphStyle('Sc',fontSize=13,fontName='Helvetica-Bold',textColor=colors.HexColor('#c9a84c'),spaceBefore=14,spaceAfter=6)
    foot_style   = ParagraphStyle('F',fontSize=9,fontName='Helvetica',textColor=colors.HexColor('#999999'),alignment=TA_CENTER)
    story += [Paragraph("AutoBid Pro",title_style),Paragraph("Vehicle Inspection Report",sub_style),
              Paragraph(f"Generated: {datetime.now().strftime('%d %B %Y, %I:%M %p')}",sub_style),
              Spacer(1,0.3*cm),HRFlowable(width="100%",thickness=2,color=colors.HexColor('#c9a84c')),Spacer(1,0.4*cm)]
    story.append(Paragraph("Vehicle Information",section_style))
    info_data=[["Car Name",car['name'],"Brand",car['brand']],["Year",str(car['year']),"Fuel Type",car['fuel']],
               ["Color",car['color'] or 'N/A',"Transmission",car['transmission'] or 'Manual'],
               ["Engine",car['engine'] or 'N/A',"Mileage",car['mileage'] or 'N/A'],
               ["Odometer",f"{car['km']:,} km","Owners",str(car['owners'] or 1)],
               ["Registration",car['registration'] or 'N/A',"City",car['city']]]
    tbl=Table(info_data,colWidths=[4*cm,5*cm,4*cm,4.5*cm])
    tbl.setStyle(TableStyle([('BACKGROUND',(0,0),(0,-1),colors.HexColor('#f0f0f0')),('BACKGROUND',(2,0),(2,-1),colors.HexColor('#f0f0f0')),
        ('FONTNAME',(0,0),(0,-1),'Helvetica-Bold'),('FONTNAME',(2,0),(2,-1),'Helvetica-Bold'),('FONTSIZE',(0,0),(-1,-1),10),
        ('GRID',(0,0),(-1,-1),0.5,colors.HexColor('#dddddd')),('ROWBACKGROUNDS',(0,0),(-1,-1),[colors.HexColor('#f9f9f9'),colors.white]),('PADDING',(0,0),(-1,-1),7)]))
    story += [tbl,Spacer(1,0.4*cm)]
    story.append(Paragraph("Inspection Checklist",section_style))
    checks=[["Inspection Point","Status","Remarks"],["Engine Condition","Good","No oil leaks, runs smoothly"],
            ["Transmission","Good","Smooth gear shifts"],["Brakes (Front)","Good","Disc brakes in good condition"],
            ["Brakes (Rear)","Good","Drum brakes serviceable"],["Suspension","Good","No unusual noise"],
            ["Tyres (All 4)","Good","70-80% tread remaining"],["AC & Cooling","Working","Cools efficiently"],
            ["Electricals","Working","All lights & sensors functional"],["Body & Paint","Good","Minor surface scratches only"],
            ["Interior","Good","Clean, no major tears"],["Documents","Complete","RC, Insurance verified"],
            ["Chassis Number","Verified","Matches registration"],["Engine Number","Verified","Matches RC book"]]
    ct=Table(checks,colWidths=[6*cm,3.5*cm,8*cm])
    ct.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#1a1a2e')),('TEXTCOLOR',(0,0),(-1,0),colors.white),
        ('FONTNAME',(0,0),(-1,0),'Helvetica-Bold'),('FONTSIZE',(0,0),(-1,-1),10),('GRID',(0,0),(-1,-1),0.5,colors.HexColor('#dddddd')),
        ('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.HexColor('#f9fff9'),colors.white]),('PADDING',(0,0),(-1,-1),7),
        ('TEXTCOLOR',(1,1),(1,-1),colors.HexColor('#2e7d32')),('FONTNAME',(1,1),(1,-1),'Helvetica-Bold'),('ALIGN',(1,0),(1,-1),'CENTER')]))
    story += [ct,Spacer(1,0.4*cm)]
    story.append(Paragraph("Pricing Summary",section_style))
    base=car['price']; tax=base*0.05; rto=base*0.02; ins=18500; total=base+tax+rto+ins
    price_data=[["Component","Amount"],["Base Vehicle Price",f"Rs.{base:,.0f}"],["GST (5%)",f"Rs.{tax:,.0f}"],
                ["RTO Registration (2%)",f"Rs.{rto:,.0f}"],["Insurance (1 Year)",f"Rs.{ins:,.0f}"],["Total On-Road Price",f"Rs.{total:,.0f}"]]
    pt=Table(price_data,colWidths=[10*cm,7.5*cm])
    pt.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#1a1a2e')),('TEXTCOLOR',(0,0),(-1,0),colors.white),
        ('FONTNAME',(0,0),(-1,0),'Helvetica-Bold'),('FONTNAME',(0,-1),(-1,-1),'Helvetica-Bold'),
        ('BACKGROUND',(0,-1),(-1,-1),colors.HexColor('#c9a84c')),('TEXTCOLOR',(0,-1),(-1,-1),colors.white),
        ('FONTSIZE',(0,0),(-1,-1),11),('GRID',(0,0),(-1,-1),0.5,colors.HexColor('#dddddd')),
        ('ROWBACKGROUNDS',(0,1),(-1,-2),[colors.HexColor('#f9f9f9'),colors.white]),('PADDING',(0,0),(-1,-1),8),('ALIGN',(1,0),(1,-1),'RIGHT')]))
    story += [pt,Spacer(1,0.6*cm),HRFlowable(width="100%",thickness=1,color=colors.HexColor('#dddddd')),Spacer(1,0.3*cm),
              Paragraph("This report was generated by AutoBid Pro. Valid for 30 days from generation date.",foot_style),
              Paragraph("For queries: support@autobidpro.in | 1800-AUTOBID",foot_style)]
    doc.build(story)
    buffer.seek(0)
    return send_file(buffer,as_attachment=True,download_name=f"Inspection_{car['name'].replace(' ','_')}_{car['year']}.pdf",mimetype='application/pdf')

if __name__=="__main__":
    init_db(); app.run(debug=True,port=5000)