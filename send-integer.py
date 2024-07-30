from flask import Flask, jsonify
from datetime import datetime

app = Flask(__name__)


@app.route("/count", methods=["GET"])
def count():
    in_count = 0
    today = datetime.today().strftime("%Y-%m-%d") 
    with open("people_count.csv", "r") as count_file:
        for line in count_file:
            if today in line and "IN" in line:
                in_count += 1
    return jsonify({"value": in_count})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
