import os
from flask import Flask, request, jsonify
from flask_cors import CORS
from models import db, SurveyResponse
from scorer import score_payload, normalize_and_numeric, make_code
from flask import abort

app = Flask(__name__, instance_relative_config=True)
CORS(app)

os.makedirs(app.instance_path, exist_ok=True)

db_path = os.path.join(app.instance_path, "app.db")
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///" + db_path
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db.init_app(app)

with app.app_context():
    db.create_all()

@app.route("/")
def home():
    return {"status": "Flask is running!"}

@app.route("/score", methods=["POST"])
def score():
    payload = request.get_json(force=True) or {}
    mapped = normalize_and_numeric(payload)
    result = score_payload(mapped)
    code = make_code()
    result["code"] = code
    row = SurveyResponse.from_payload(mapped, result)
    db.session.add(row)
    db.session.commit()
    return jsonify(result), 200

if __name__ == "__main__":
    app.run(debug=True)

@app.route("/health")
def health():
    return {"ok": True, "version": "0.1.0"}

from flask import abort

@app.route("/results/<code>", methods=["GET"])
def results(code):
    row = SurveyResponse.query.filter_by(cluster_code=code).first()
    if not row:
        abort(404, description="Code not found")

    return {
        "code": code,
        "total_dependency": row.total_dependency,
        "total_dependency_pct": row.total_dependency_pct,
        "cluster": row.cluster,
        "confidence_mean": row.conf_mean,
        "productivity_mean": row.prod_mean,
        # add more if needed
    }, 200
