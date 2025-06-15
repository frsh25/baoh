from flask import (
    Flask,
    redirect,
    render_template,
    request,
    jsonify,
    session,
    send_file,
    url_for,
    abort,
    flash,
    Response,
)
from flask_login import LoginManager, login_required
from pymongo import MongoClient
import pandas as pd
import os, re, pickle, requests, time, io, csv, uuid, json, base64
from sklearn.feature_extraction.text import TfidfVectorizer
from collections import Counter
from bson import ObjectId
from datetime import datetime, timezone, timedelta
from werkzeug.security import generate_password_hash, check_password_hash
from flask_wtf.csrf import CSRFProtect
from functools import wraps
from bidi.algorithm import get_display
import arabic_reshaper
import google.generativeai as genai
import facebook
import matplotlib.pyplot as plt
from fpdf import FPDF
from urllib.parse import urlparse, parse_qs
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# ✅ تحديد المسار الأساسي للمشروع بشكل ديناميكي
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# إعداد التطبيق
app = Flask(__name__, template_folder="templates")
app.secret_key = "super-secret-key"
# app.config['SESSION_COOKIE_SECURE'] = True
# ----------------- الاتصال بقاعدة البيانات -----------------
try:
    client = MongoClient("mongodb://localhost:27017/")
    db = client["asa"]
    collection = db["ana_csv"]
    collection_chat = db["chat"]
    reports_collection = db["reports"]
    text_collection = db["text"]
    result_collection = db["text_result"]
    fb_reports_collection = db["fb_reports"]
    link_collection = db["link"]
    facebook_api_collection = db["facebook_api"]
    link_result_collection = db["link_result"]
    comment_collection = db["comment"]
    users_collection = db["user"]
    col_instagram_api = db["instagram_api"]
    col_in_report = db["in_report"]
    col_comment_inst = db["comment_inst"]
    yt_link_col = db["link_youtube"]
    yt_comment_col = db["comment_yout"]
    yt_link_result_col = db["link_result_youtube"]
    yt_report_col = db["yout_report"]
    admin_collection = db["admin"]
    print("✅ تم الاتصال بنجاح مع MongoDB!")
except Exception as e:
    print(f"❌ فشل في الاتصال بقاعدة البيانات MongoDB: {e}")




# ----------------- تحميل النموذج و TF-IDF -----------------
try:
    with open(os.path.join(BASE_DIR, "logistic_regression_model.pkl"), "rb") as f:
        model = pickle.load(f)
    with open(os.path.join(BASE_DIR, "tfidf_vectorizer.pkl"), "rb") as f:
        vectorizer = pickle.load(f)
    print("✅ تم تحميل النموذج و Vectorizer بنجاح!")
except Exception as e:
    print(f"❌ خطأ في تحميل النموذج أو الـ Vectorizer: {e}")



# ----------------- إعداد Gemini API -----------------
API_KEY = "AIzaSyBewEcbCEJUXEFIzpRwgo2JbZCzMgpV-60"
genai.configure(api_key=API_KEY)
gemini_model = genai.GenerativeModel("models/gemini-1.5-flash-latest")
chats = {} 

# ----------------- مزخرف التحقق من صلاحيات المدير (باستخدام الجلسة) -----------------
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "admin_id" not in session:
            flash("يجب تسجيل الدخول كمدير للوصول إلى هذه الصفحة.", "warning")
            return redirect(url_for("ad_login", next=request.url))
        return f(*args, **kwargs)

    return decorated_function




# مسار تسجيل الحساب
app.config["SESSION_COOKIE_SECURE"] = True


# ----------------- صفحات HTML -----------------
@app.route("/")
def home():
    return render_template("home.html")


@app.route("/admin")
@admin_required
def admin():
    return render_template("admain.html")

stop_words = set(
    [
        "في",
        "من",
        "إلى",
        "عن",
        "على",
        "مع",
        "ذلك",
        "لكن",
        "أيضا",
        "لذلك",
        "أن",
        "هو",
        "هي",
        "كان",
        "تكون",
        "ليس",
        "و",
        "أو",
        "كما",
        "ماذا",
        "أين",
        "هل",
    ]
)

def extract_top_keywords(posts):
    all_text = " ".join(post["csv_text"] for post in posts)
    all_text = re.sub(r"[^\w\s]", "", all_text)
    all_text = re.sub(r"\d+", "", all_text)
    words = all_text.split()
    filtered_words = [word for word in words if word not in stop_words]
    word_counts = Counter(filtered_words)
    top_keywords = [
        word for word, _ in word_counts.most_common(5)
    ]  
    return top_keywords


@app.route("/admain")
@admin_required
def admainn():
    positive_count = collection.count_documents({"csv_prediction": "positive"})
    negative_count = collection.count_documents({"csv_prediction": "negative"})
    neutral_count = collection.count_documents({"csv_prediction": "neutral"})
    total_posts = positive_count + negative_count + neutral_count
    latest_posts = list(collection.find().sort("csv_date_uploaded", -1).limit(10))

    labels = []
    positive_data = []
    negative_data = []
    neutral_data = []

    today = datetime.now(timezone.utc).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    for i in range(6, -1, -1):
        day_date = today - timedelta(days=i)
        next_day_date = day_date + timedelta(days=1)

        day_name_ar = [
            "الإثنين",
            "الثلاثاء",
            "الأربعاء",
            "الخميس",
            "الجمعة",
            "السبت",
            "الأحد",
        ][day_date.weekday()]
        labels.append(day_name_ar)

        query = {"csv_date_uploaded": {"$gte": day_date, "$lt": next_day_date}}

        pos_day_count = collection.count_documents(
            {**query, "csv_prediction": "positive"}
        )
        neg_day_count = collection.count_documents(
            {**query, "csv_prediction": "negative"}
        )
        neu_day_count = collection.count_documents(
            {**query, "csv_prediction": "neutral"}
        )

        positive_data.append(pos_day_count)
        negative_data.append(neg_day_count)
        neutral_data.append(neu_day_count)

    sentiment_data = {
        "labels": labels,
        "positive": positive_data,
        "negative": negative_data,
        "neutral": neutral_data,
    }
    top_keywords = extract_top_keywords(latest_posts)

    return render_template(
        "admain.html",
        positive_count=positive_count,
        negative_count=negative_count,
        neutral_count=neutral_count,
        total_posts=total_posts,
        latest_posts=latest_posts,
        sentiment_data=sentiment_data,
        top_keywords=top_keywords,
    )

# --------------------تسجيل--------------------------
@app.route("/signup_ad", methods=["GET", "POST"])
def signup_ad():
    if request.method == "POST":
        username = request.form["username"]
        email = request.form["email"]
        password = request.form["password"]
        confirm_password = request.form["confirm_password"]

        admin_collection = db["admin"]
        existing_admin_count = admin_collection.count_documents({})
        if existing_admin_count >= 2:
            flash("لا يمكن إنشاء أكثر من أدمن واحد.", "error")
            return redirect(url_for("signup_ad"))

        if password != confirm_password:
            flash("كلمتا المرور غير متطابقتين!", "error")
            return redirect(url_for("signup_ad"))

        existing_admin = admin_collection.find_one({"email": email})
        if existing_admin:
            flash("البريد الإلكتروني مستخدم بالفعل.", "error")
            return redirect(url_for("signup_ad"))

        hashed_password = generate_password_hash(password)

        admin_data = {"username": username, "email": email, "password": hashed_password}
        admin_collection.insert_one(admin_data)

        flash("تم إنشاء حساب المدير بنجاح! يمكنك الآن تسجيل الدخول.", "success")
        return redirect(url_for("ad_login"))

    return render_template("signup_ad.html")


@app.route("/ad_login", methods=["GET", "POST"])
@app.route("/ad_login", methods=["GET", "POST"])
def ad_login():
    if request.method == "POST":
        username = request.form["username"]
        pwd = request.form["password"]
        admin = admin_collection.find_one({"username": username})
        if admin and check_password_hash(admin["password"], pwd):
            session["admin_id"], session["admin_username"] = (
                str(admin["_id"]),
                admin["username"],
            )
            flash("تم تسجيل الدخول.", "success")
            return redirect(url_for("admain"))
        else:
            flash("بيانات خاطئة.", "error")
            return render_template("ad_login.html")
    return render_template("ad_login.html")


@app.route("/admain")
def admain():
    if "admin_id" not in session:
        flash("يرجى تسجيل الدخول أولاً", "error")
        return redirect(url_for("ad_login"))

    return render_template("admain.html", admin_username=session["admin_username"])

@app.route("/forgit")
def forgit():
    return render_template("forgit.html")

# ----------------- الصفحات الرئيسية للمستخدم (متاحة للجميع) -----------------
@app.route("/index")
def index():
    return render_template("index.html")

@app.route("/analysis")
def analysis():
    return render_template("analysis.html")

@app.route("/anafti")
def anafti():
    return render_template("anafti.html")

@app.route("/insta")
def insta():
    return render_template("insta.html")

@app.route("/ana_csv")
def ana_csv():
    return render_template("ana_csv.html")

@app.route("/youtube")
def youtube_page():
    return render_template("youtube.html")

@app.route("/vid_inst")
def vid_inst():
    return render_template("vid_inst.html")

@app.route("/vid_face")
def vid_face():
    return render_template("vid_face.html")

@app.route("/vid_yout")
def vid_yout():
    return render_template("vid_yout.html")

# -----------------صفحات تسجيل الدخول/الخروج  -----------------

@app.route("/settings", methods=["GET", "POST"])
@admin_required 
def settings():
    admin_collection = db["admin"]
    admin_id = session.get("admin_id")

    if not admin_id:
        flash("يجب تسجيل الدخول كمدير للوصول إلى الإعدادات.", "warning")
        return redirect(url_for("ad_login"))

    admin_data = admin_collection.find_one({"_id": ObjectId(admin_id)})

    if request.method == "POST":
        action = request.form.get("action")

        if action == "update_profile":
            new_email = request.form.get("admin-email")

            if not new_email:
                flash("البريد الإلكتروني مطلوب.", "error")
            else:
                existing_admin = admin_collection.find_one(
                    {"email": new_email, "_id": {"$ne": ObjectId(admin_id)}}
                )
                if existing_admin:
                    flash("البريد الإلكتروني مستخدم بالفعل.", "error")
                else:
                    admin_collection.update_one(
                        {"_id": ObjectId(admin_id)}, {"$set": {"email": new_email}}
                    )
                    flash("تم تحديث البيانات بنجاح.", "success")

        elif action == "change_password":
            current_password = request.form.get("current-password")
            new_password = request.form.get("new-password")
            confirm_password = request.form.get("confirm-password")

            if not current_password or not new_password or not confirm_password:
                flash("جميع حقول كلمة المرور مطلوبة.", "error")
            elif new_password != confirm_password:
                flash("كلمة المرور الجديدة وتأكيدها غير متطابقين.", "error")
            elif not check_password_hash(admin_data["password"], current_password):
                flash("كلمة المرور الحالية غير صحيحة.", "error")
            else:
                hashed_password = generate_password_hash(new_password)
                admin_collection.update_one(
                    {"_id": ObjectId(admin_id)}, {"$set": {"password": hashed_password}}
                )
                flash("تم تغيير كلمة المرور بنجاح.", "success")

    return render_template("settings.html", admin=admin_data)


# ----------------- وظائف مشتركة -----------------
def run_apify_task(token, post_url, limit=50, wait=5):
    actor = f"https://api.apify.com/v2/acts/apify~instagram-comment-scraper/runs?token={token}"
    payload = {"directUrls": [post_url], "resultsLimit": limit}
    r = requests.post(actor, json=payload)
    r.raise_for_status()
    run_id = r.json()["data"]["id"]
    status_url = f"https://api.apify.com/v2/actor-runs/{run_id}?token={token}"
    while True:
        st = requests.get(status_url).json()["data"]["status"]
        if st in ("SUCCEEDED", "FAILED"):
            break
        time.sleep(wait)
    if st != "SUCCEEDED":
        raise Exception("Apify task failed")
    ds_id = requests.get(status_url).json()["data"]["defaultDatasetId"]
    items_url = (
        f"https://api.apify.com/v2/datasets/{ds_id}/items?token={token}&format=json"
    )
    return requests.get(items_url).json()


# ----------------- خريطة التسمية والإيموجي -----------------
LABELS = {1: ("إيجابي", "😊"), 0: ("محايد", "😐"), -1: ("سلبي", "😞")}

# ----------------- دوال مساعدة لليوتيوب -----------------
def extract_identifier(raw):
    parsed = urlparse(raw)
    if parsed.hostname and "youtube.com" in parsed.hostname:
        qs = parse_qs(parsed.query)
        if "list" in qs:
            return qs["list"][0], "playlist"
        if "v" in qs:
            return qs["v"][0], "video"
    if parsed.hostname and "youtu.be" in parsed.hostname:
        return parsed.path.lstrip("/"), "video"
    if raw.startswith("PL"):
        return raw, "playlist"
    return raw, "video"


def get_video_ids_from_playlist(youtube, playlist_id):
    video_ids = []
    req = youtube.playlistItems().list(
        part="contentDetails", playlistId=playlist_id, maxResults=50
    )
    while req:
        res = req.execute()
        for item in res.get("items", []):
            video_ids.append(item["contentDetails"]["videoId"])
        req = youtube.playlistItems().list_next(req, res)
    return video_ids


def get_comments_for_video(youtube, video_id):
    comments = []
    req = youtube.commentThreads().list(
        part="snippet", videoId=video_id, maxResults=100, textFormat="plainText"
    )
    while req:
        res = req.execute()
        for item in res.get("items", []):
            cid = item["snippet"]["topLevelComment"]["id"]
            txt = item["snippet"]["topLevelComment"]["snippet"]["textDisplay"]
            comments.append({"id": cid, "text": txt})
            if item["snippet"]["totalReplyCount"] > 0:
                rep = youtube.comments().list(
                    part="snippet",
                    parentId=item["id"],
                    maxResults=100,
                    textFormat="plainText",
                )
                while rep:
                    rres = rep.execute()
                    for r in rres.get("items", []):
                        comments.append(
                            {"id": r["id"], "text": r["snippet"]["textDisplay"]}
                        )
                    rep = youtube.comments().list_next(rep, rres)
        req = youtube.commentThreads().list_next(req, res)
    return comments


def analyze_comments(comments):
    X = vectorizer.transform([c["text"] for c in comments])
    preds = model.predict(X)
    label_map = {-1: "سلبي", 0: "محايد", 1: "إيجابي"}
    return pd.DataFrame(
        {
            "commentId": [c["id"] for c in comments],
            "comment_text": [c["text"] for c in comments],
            "sentiment_label": [label_map[p] for p in preds],
        }
    )


# -------------------تسجيل الدخول---------------------------
@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        username = request.form["username"]
        email = request.form["email"]
        phone = request.form["phone"]
        password = request.form["password"]

        if users_collection.find_one({"user_email": email}):
            flash("البريد الإلكتروني موجود بالفعل!")
            return redirect(url_for("signup"))

        hashed_password = generate_password_hash(password)
        users_collection.insert_one(
            {
                "user_name": username,
                "user_email": email,
                "user_phone": phone,
                "user_password": hashed_password,
            }
        )

        flash("تم إنشاء الحساب بنجاح! يمكنك الآن تسجيل الدخول.")
        return redirect(url_for("login"))  

    return render_template("signup.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        user = users_collection.find_one({"user_name": username})

        if user and check_password_hash(user["user_password"], password):
            flash("مرحباً بك!", "success")
            return redirect(
                url_for("index")
            )  
        else:
            flash("اسم المستخدم أو كلمة المرور غير صحيحة", "danger")
            return redirect(url_for("login"))

    return render_template("login.html")


# ----------------- صفحة إدارة المستخدمين -----------------
from flask import render_template


@app.route("/users")
def users():
    all_users = users_collection.find()
    return render_template("users.html", users=all_users)


@app.route("/delete_user/<user_id>", methods=["POST"])
def delete_user(user_id):
    try:
        users_collection.delete_one({"_id": ObjectId(user_id)})
        print(f"✅ تم حذف المستخدم ذو المعرف: {user_id}")
    except Exception as e:
        print(f"❌ خطأ أثناء حذف المستخدم: {e}")
    return redirect(url_for("users"))


# ----------------- API لاستخراج أعمدة CSV -----------------
@app.route("/get_columns", methods=["POST"])
def get_columns():
    file = request.files.get("file")
    if not file:
        return jsonify({"error": "لم يتم إرسال أي ملف"}), 400
    try:
        df = pd.read_csv(file)
        object_columns = df.select_dtypes(include=["object"]).columns.tolist()
        return jsonify({"columns": object_columns})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/ana_csv", methods=["POST"])
def ana_csv_handler():
    file = request.files.get("file")
    text_column = request.form.get("selected_column")
    if not file or not text_column:
        return "❌ يرجى رفع الملف واختيار العمود النصي."

    try:
        df = pd.read_csv(file)
    except Exception as e:
        return f"❌ خطأ في قراءة الملف: {str(e)}"

    if text_column not in df.columns:
        return f"❌ العمود '{text_column}' غير موجود في الملف."

    df_sampled = df.sample(n=min(500, len(df)), random_state=42)
    texts = df_sampled[text_column].astype(str).fillna("")

    X = vectorizer.transform(texts)
    raw_preds = model.predict(X)
    mapping = {-1: "negative", 1: "positive", 0: "neutral"}
    preds = [mapping.get(p, p) for p in raw_preds]
    counter = Counter(preds)

    csv_id = str(ObjectId())
    
    result_data = []
    current_time = datetime.utcnow()
    for text, pred in zip(texts, preds):
        result_data.append(
            {
                "csv_id": csv_id,
                "csv_text": text,
                "csv_prediction": pred,
                "csv_date_uploaded": current_time,
                "csv_source_file": file.filename,
            }
        )
    collection.insert_many(result_data)

    total = len(df)
    average_score = round(
        sum(1 if p == "positive" else -1 if p == "negative" else 0 for p in preds)
        / len(preds),
        2,
    )

    bar_chart_config = {
        "type": "bar",
        "data": {
            "labels": ["إيجابي", "سلبي", "محايد"],
            "datasets": [
                {
                    "label": "عدد المشاعر",
                    "data": [
                        counter.get("positive", 0),
                        counter.get("negative", 0),
                        counter.get("neutral", 0),
                    ],
                }
            ],
        },
    }

    return render_template(
        "ana_csv.html",
        message=f"✅ تم تحليل {len(preds)} صفًا من أصل {total} صفًا.",
        num_rows=len(df_sampled),
        num_columns=len(df.columns),
        total=len(df),
        average=average_score,
        positive_count=counter.get("positive", 0),
        negative_count=counter.get("negative", 0),
        neutral_count=counter.get("neutral", 0),
        bar_chart_data=bar_chart_config,
        csv_id=csv_id,
    )


@app.route("/save_report", methods=["POST"])
def save_report():
    try:
        data = request.get_json()
        csv_id = data["csv_id"]

        header, encoded = data["chart_image"].split(",", 1)
        img_data = base64.b64decode(encoded)
        img_filename = f"{csv_id}.png"
        img_path = os.path.join("static", "reports", img_filename)
        os.makedirs(os.path.dirname(img_path), exist_ok=True)
        with open(img_path, "wb") as f:
            f.write(img_data)

        df_report = pd.DataFrame(list(collection.find({"csv_id": csv_id}, {"_id": 0})))
        csv_filename = f"{csv_id}.csv"
        csv_path = os.path.join("static", "reports", csv_filename)
        df_report.to_csv(csv_path, index=False)

        def reshape_arabic(text):
            reshaped_text = arabic_reshaper.reshape(text)
            bidi_text = get_display(reshaped_text)
            return bidi_text

        pdf = FPDF()
        pdf.add_page()

        font_path = os.path.join(
            "static", "fonts", "NotoSansArabic_Condensed-Regular.ttf"
        )
        if not os.path.exists(font_path):
            return jsonify({"status": "error", "error": "⚠️ ملف الخط غير موجود"}), 500

        pdf.add_font("NotoArabic", "", font_path, uni=True)
        pdf.set_font("NotoArabic", "", 14)

        title = reshape_arabic("تقرير التحليل")
        pdf.cell(0, 10, txt=title, ln=True, align="C")
        pdf.ln(10)

        pdf.set_font("NotoArabic", size=12)
        pdf.cell(
            0,
            8,
            txt=reshape_arabic(f"عدد الصفوف: {data['num_rows']}"),
            ln=True,
            align="R",
        )
        pdf.cell(
            0,
            8,
            txt=reshape_arabic(f"عدد الأعمدة: {data['num_columns']}"),
            ln=True,
            align="R",
        )
        pdf.cell(
            0, 8, txt=reshape_arabic(f"المجموع: {data['total']}"), ln=True, align="R"
        )
        pdf.cell(
            0, 8, txt=reshape_arabic(f"المتوسط: {data['average']}"), ln=True, align="R"
        )
        pdf.ln(10)

        if os.path.exists(img_path):
            pdf.image(img_path, x=10, y=None, w=180)
        else:
            pdf.cell(0, 10, txt="⚠️ لم يتم العثور على صورة المخطط", ln=True, align="C")

        pdf_filename = f"{csv_id}.pdf"
        pdf_path = os.path.join("static", "reports", pdf_filename)
        pdf.output(pdf_path)

        report_id = str(ObjectId())
        report_doc = {
            "report_id": report_id,
            "csv_id": csv_id,
            "generated_at": datetime.now(timezone.utc),
            "num_rows": data["num_rows"],
            "num_columns": data["num_columns"],
            "total": data["total"],
            "average": data["average"],
            "report_paths": {
                "png_path": img_path,
                "csv_path": csv_path,
                "pdf_path": pdf_path,
            },
        }
        reports_collection.update_one(
            {"csv_id": csv_id}, {"$set": report_doc}, upsert=True
        )

        return jsonify(
            {
                "status": "success",
                "report_id": report_id,
                "csv_id": csv_id,
                "png_url": url_for("static", filename=f"reports/{img_filename}"),
                "csv_url": url_for("static", filename=f"reports/{csv_filename}"),
                "pdf_url": url_for("static", filename=f"reports/{pdf_filename}"),
            }
        )

    except Exception as e:
        return jsonify({"status": "error", "error": str(e)}), 500


@app.route("/download/pdf/<csv_id>")
def download_pdf(csv_id):
    try:
        pdf_path = os.path.join("static", "reports", f"{csv_id}.pdf")
        if os.path.exists(pdf_path):
            return send_file(pdf_path, as_attachment=True)
        else:
            return "❌ لم يتم العثور على ملف PDF", 404
    except Exception as e:
        return f"❌ حدث خطأ أثناء تحميل PDF: {str(e)}", 500


@app.route("/download/png")
def download_png():
    collection = db.ana_csv
    data = list(collection.find())
    df = pd.DataFrame(data)

    if "prediction" in df.columns:
        plt.figure(figsize=(8, 6))
        df["prediction"].value_counts().plot(kind="bar", color="skyblue")
        plt.title("توزيع التوقعات")
        plt.ylabel("العدد")
        plt.tight_layout()

        img = io.BytesIO()
        plt.savefig(img, format="png")
        img.seek(0)
        return send_file(
            img, mimetype="image/png", as_attachment=True, download_name="report.png"
        )
    else:
        return "لا توجد بيانات مناسبة للرسم", 400


# ------------------- صفحة تحليل نص----------------------
@app.route("/ana_text", methods=["GET", "POST"])
def ana_text():
    if request.method == "POST":
        text_input = request.form["text_input"].strip()
        if not text_input:
            return render_template("ana_text.html", error="❌ الرجاء إدخال نص.")

        text_vectorized = vectorizer.transform([text_input])
        raw = model.predict(text_vectorized)[0]
        sentiment_label = {1: "إيجابي", -1: "سلبي"}.get(raw, "محايد")

        now = datetime.now()
        analysis_date = now.strftime("%Y-%m-%d")
        analysis_time = now.strftime("%H:%M:%S")

        text_id = str(uuid.uuid4())

        text_doc = {
            "_id": ObjectId(), 
            "text_id": text_id,
            "text_input": text_input,
            "text_analysisdate": analysis_date,
            "text_analysistime": analysis_time,
        }
        text_collection.insert_one(text_doc)

        result_doc = {
            "_id": ObjectId(),
            "text_analysis_result_id": str(uuid.uuid4()),
            "text_analysis_result": sentiment_label,
            "text_id": text_id,  
        }
        result_collection.insert_one(result_doc)

        return render_template(
            "ana_text.html", sentiment=sentiment_label, text=text_input
        )

    return render_template("ana_text.html")


# ----------------- دوال مساعدة لتحليل فيسبوك -----------------
def extract_post_id(url: str) -> str:
    m = re.search(r"story_fbid=(\d+)&id=(\d+)", url)
    if m:
        return f"{m.group(2)}_{m.group(1)}"

    m = re.search(r"/(\d+)/posts/(\d+)", url)
    if m:
        return f"{m.group(1)}_{m.group(2)}"

    m = re.search(r"[?&]fbid=(\d+)", url)
    if m:
        return m.group(1)

    m = re.search(r"/videos/(\d+)", url)
    if m:
        return m.group(1)

    raise ValueError(
        "رابط غير صالح: الرجاء استخدام رابط منشور، صورة، أو فيديو صحيح يحتوي على fbid أو posts أو videos"
    )


def fetch_all_comments(graph, post_id: str):
    comments = []
    page = graph.get_connections(
        id=post_id,
        connection_name="comments",
        fields="message,created_time,id",
        limit=100,
    )
    while True:
        for c in page.get("data", []):
            comments.append(
                {
                    "id": c.get("id"),
                    "comment_text": c.get("message", "").replace("\n", " "),
                    "comment_date": c.get("created_time"),
                }
            )
        next_url = page.get("paging", {}).get("next")
        if not next_url:
            break
        page = requests.get(next_url).json()
    return comments


# ----------------- تحليل فيسبوك -----------------
@app.route("/api/comments", methods=["POST"])
def api_comments():
    data = request.get_json()
    token = data.get("token")
    postUrl = data.get("postUrl")
    try:
        post_id = extract_post_id(postUrl)
    except ValueError as ve:
        return jsonify({"error": str(ve)}), 400

    try:
        graph = facebook.GraphAPI(access_token=token, version="3.1")
    except facebook.GraphAPIError as gae:
        return jsonify({"error": "فشل في التحقق من التوكن: " + str(gae)}), 401

    try:
        comments = fetch_all_comments(graph, post_id)
    except facebook.GraphAPIError as gae:
        return jsonify({"error": "خطأ بجلب التعليقات: " + str(gae)}), 401

    texts = [c["comment_text"] for c in comments]
    X = vectorizer.transform(texts)
    preds = model.predict(X)
    emoji_map = {1: "😃ايجابي", 0: "😐محايد", -1: "😢سلبي"}
    for c, p in zip(comments, preds):
        c["sentiment"] = int(p)
        c["emoji"] = emoji_map[p]

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{post_id}_{ts}.csv"
    csv_path = os.path.join(BASE_DIR, filename)
    pd.DataFrame(comments).to_csv(csv_path, index=False, encoding="utf-8-sig")

    facebook_api_collection.insert_one({"facebook_posts": postUrl})
    fb_reports_collection.insert_one(
        {
            "report_id": filename.replace(".csv", ""),
            "postId": post_id,
            "generatedAt": datetime.now(timezone.utc),
            "totalComments": len(comments),
            "positiveCount": sum(1 for p in preds if p == 1),
            "negativeCount": sum(1 for p in preds if p == -1),
            "neutralCount": sum(1 for p in preds if p == 0),
        }
    )
    link_collection.insert_one(
        {"link_id": filename.replace(".csv", ""), "link_input": postUrl}
    )
    link_result_collection.insert_one(
        {
            "link_analysis_result_id": filename.replace(".csv", ""),
            "link_analysis_result": json.dumps(
                {
                    "+": sum(1 for p in preds if p == 1),
                    "-": sum(1 for p in preds if p == -1),
                    "0": sum(1 for p in preds if p == 0),
                }
            ),
        }
    )
    for c in comments:
        comment_collection.insert_one(
            {
                "comment_id": c["id"],
                "comment_date": c["comment_date"],
                "comment_text": c["comment_text"],
                "sentiment": c["sentiment"],
                "emoji": c["emoji"],
            }
        )

    return jsonify({"comments": comments, "filename": filename})


@app.route("/api/comments/export")
def api_export():
    csv_files = [f for f in os.listdir(BASE_DIR) if f.lower().endswith(".csv")]
    if not csv_files:
        abort(404, description="لا يوجد ملف CSV للتصدير.")
    latest_csv = sorted(csv_files)[-1]
    return send_file(
        os.path.join(BASE_DIR, latest_csv),
        as_attachment=True,
        download_name=latest_csv,
        mimetype="text/csv",
    )


# ----------------- صفحة انستجرام -----------------
@app.route("/insta/comments", methods=["POST"])
def insta_comments():
    data = request.get_json() or {}
    token = data.get("token", "").strip()
    postUrl = data.get("postUrl", "").strip()
    if not token or not postUrl:
        return jsonify(error="يرجى تقديم الرمز ورابط المنشور."), 400
    items = run_apify_task(token, postUrl)
    col_instagram_api.insert_one(
        {"instagram_posts": postUrl, "instagram_comments": len(items)}
    )
    now = datetime.now()
    link_id = str(
        link_collection.insert_one(
            {
                "link_input": postUrl,
                "link_analysisdate": now.strftime("%Y-%m-%d"),
                "link_analysistime": now.strftime("%H:%M:%S"),
            }
        ).inserted_id
    )
    results = []
    counts = {"إيجابي": 0, "سلبي": 0, "محايد": 0}
    for it in items:
        txt = it.get("text", "")
        cid = it.get("id", "")
        pred = model.predict(vectorizer.transform([txt]))[0]
        lab, emo = LABELS.get(pred, ("محايد", "😐"))
        counts[lab] += 1
        results.append(
            {
                "comment_id": cid,
                "comment_text": txt,
                "sentiment_label": lab,
                "sentiment_emoji": emo,
            }
        )
    lr_id = str(
        link_result_collection.insert_one(
            {"link_analysis_result_id": link_id, "link_analysis_result": counts}
        ).inserted_id
    )
    pc = lambda n: round(n * 100 / len(results), 2) if results else 0
    col_in_report.insert_one(
        {
            "report_id": f"{postUrl.split('/')[-2]}_{now.strftime('%Y%m%d%H%M%S')}",
            "postId": postUrl.split("/")[-2],
            "generatedAt": now,
            "totalComments": len(results),
            "positiveCount": counts["إيجابي"],
            "positivePercentage": pc(counts["إيجابي"]),
            "negativeCount": counts["سلبي"],
            "negativePercentage": pc(counts["سلبي"]),
            "neutralCount": counts["محايد"],
            "neutralPercentage": pc(counts["محايد"]),
        }
    )
    for r in results:
        col_comment_inst.insert_one(
            {
                "comment_id": r["comment_id"],
                "comment_text": r["comment_text"],
                "user_id": r.get("user_id", ""),
                "sentiment_label": r["sentiment_label"],
                "sentiment_emoji": r["sentiment_emoji"],
                "link_analysis_result_id": lr_id,
                "text_analysis_result_id": None,
            }
        )
    return jsonify(comments=results)


# ----------------- مصدّر CSV للانستجرام -----------------
@app.route("/insta/comments/export")
def insta_export():
    """صدّر جميع تعليقات إنستجرام إلى CSV مع تعويض القيم المفقودة."""
    si = io.StringIO()
    w = csv.writer(si)
    w.writerow(["comment_id", "comment_text", "sentiment_label", "sentiment_emoji"])
    for c in col_comment_inst.find():
        w.writerow(
            [
                c.get("comment_id", ""),
                c.get("comment_text", ""),
                c.get("sentiment_label", ""),
                c.get("sentiment_emoji", ""),
            ]
        )
    output = si.getvalue().encode("utf-8-sig")
    return Response(
        output,
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=instagram_comments.csv"},
    )


# ----------------- مسار تحليل يوتيوب -----------------
@app.route("/youtube/analyze", methods=["POST"])
def youtube_analyze():
    data = request.get_json() or {}
    key = data.get("apiKey", "").strip()
    raw_id = data.get("identifier", "").strip()
    if not key or not raw_id:
        return jsonify(error="يرجى إدخال مفتاح API والمعرف أو الرابط."), 400

    vid_or_pl, kind = extract_identifier(raw_id)
    run_id = str(uuid.uuid4())
    now = datetime.utcnow()
    yt_link_col.insert_one(
        {
            "link_id": run_id,
            "link_input": raw_id,
            "link_analysisdate": now.strftime("%Y-%m-%d"),
            "link_analysistime": now.strftime("%H:%M:%S"),
        }
    )
    try:
        yt = build("youtube", "v3", developerKey=key)
        vids = (
            get_video_ids_from_playlist(yt, vid_or_pl)
            if kind == "playlist"
            else [vid_or_pl]
        )
        comments = []
        for vid in vids:
            comments.extend(get_comments_for_video(yt, vid))
        if not comments:
            return jsonify(error="لا توجد تعليقات."), 200

        df = analyze_comments(comments)
        for _, row in df.iterrows():
            yt_comment_col.insert_one(
                {
                    "link_id": run_id,  
                    "videoId": vid_or_pl if kind == "video" else None,
                    "playlistId": vid_or_pl if kind == "playlist" else None,
                    "commentId": row["commentId"],
                    "text": row["comment_text"],
                    "sentiment": row["sentiment_label"],
                    "analyzedAt": now,
                    "sourceRaw": raw_id,
                    "kind": kind,
                }
            )
            yt_link_result_col.insert_one(
                {
                    "link_analysis_result_id": row["commentId"],
                    "link_analysis_result": row["sentiment_label"],
                    "link_id": run_id,
                }
            )
        counts = df["sentiment_label"].value_counts().to_dict()
        rep_id = f"{run_id}_{now.strftime('%Y%m%d%H%M%S')}"
        yt_report_col.insert_one(
            {
                "report_id": rep_id,
                "videoId": vid_or_pl if kind == "video" else None,
                "playlistId": vid_or_pl if kind == "playlist" else None,
                "generatedAt": now,
                "totalComments": len(df),
                "positiveCount": counts.get("إيجابي", 0),
                "positivePercentage": counts.get("إيجابي", 0) / len(df) * 100,
                "negativeCount": counts.get("سلبي", 0),
                "negativePercentage": counts.get("سلبي", 0) / len(df) * 100,
                "neutralCount": counts.get("محايد", 0),
                "neutralPercentage": counts.get("محايد", 0) / len(df) * 100,
            }
        )
        return jsonify(comments=df.to_dict(orient="records"))
    except HttpError as e:
        return jsonify(error=f"خطأ من YouTube API: {e.resp.status}"), 500
    except Exception as ex:
        return jsonify(error=f"حدث خطأ: {ex}"), 500


# ----------------- مصدّر CSV لتحليل يوتيوب -----------------
@app.route("/youtube/export")
def youtube_export():
    last = list(yt_comment_col.find().sort("_id", -1).limit(1))
    if not last:
        return jsonify(error="لا توجد بيانات للتصدير."), 404

    link_id = last[0].get("link_id")
    if not link_id:
        return jsonify(error="لم يتم العثور على link_id في السجلات."), 500

    rows = list(yt_comment_col.find({"link_id": link_id}, {"_id": 0}))

    si = io.StringIO()
    w = csv.writer(si)
    w.writerow(["commentId", "text", "sentiment"])
    for r in rows:
        w.writerow([r["commentId"], r["text"], r["sentiment"]])
    return Response(
        si.getvalue().encode("utf-8-sig"),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=youtube_comments.csv"},
    )


# ------------------ شات بوت ------------------
@app.route("/chat")
def chat():
    return render_template("chat.html")


@app.route("/ask", methods=["POST"])
def ask():
    data = request.get_json()
    user_msg = data.get("message", "").strip()
    if not user_msg:
        return jsonify({"response": "الرجاء إرسال رسالة صالحة."}), 400

    if "session_id" not in session:
        session["session_id"] = str(uuid.uuid4())
    sid = session["session_id"]

    collection_chat.insert_one(
        {
            "session_id": sid,
            "user_message": user_msg,
            "bot_response": None,
            "timestamp": datetime.utcnow(),
        }
    )

    if sid not in chats:
        chats[sid] = gemini_model.start_chat()
    chat_obj = chats[sid]

    response = chat_obj.send_message(user_msg)
    bot_msg = response.text

    collection_chat.insert_one(
        {
            "session_id": sid,
            "user_message": None,
            "bot_response": bot_msg,
            "timestamp": datetime.utcnow(),
        }
    )

    return jsonify({"response": bot_msg})


if __name__ == "__main__":
    app.run(debug=True)


# ----------------- تسجيل الخروج -----------------
@app.route("/logout")
def logout():
    session.pop("user_id", None)
    session.pop("username", None)
    flash("تم تسجيل الخروج بنجاح.", "info")
    return redirect(url_for("home")) 


@app.route("/admin_logout")
@admin_required  
def admin_logout():
    session.pop("admin_id", None)
    session.pop("admin_username", None)
    flash("تم تسجيل خروج المدير بنجاح.", "info")
    return redirect(url_for("ad_login")) 
