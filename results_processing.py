from os import environ
from traceback import format_exc
import requests
from json import loads
from datetime import datetime
import pytz

PROJECT_ID = environ.get('GALLOPER_PROJECT_ID')
URL = environ.get('GALLOPER_URL')
REPORT_ID = environ.get('REPORT_ID')
BUCKET = environ.get("TESTS_BUCKET")
REPORTS_BUCKET = environ.get("REPORTS_BUCKET")
TEST = environ.get("ARTIFACT")
TOKEN = environ.get("token")
PATH_TO_FILE = f'/tmp/{TEST}'
TESTS_PATH = environ.get("tests_path", '/')


try:
    with open("/manifest.json", "r") as f:
        manifest = loads(f.read())
    for each in manifest:
        json_path = each['jsonPath']
        with open(json_path, "r") as f:
            json_data = loads(f.read())

            thresholds = {}
            file_name = each["htmlPath"].split("/")[-1]
            result = {
                "requests": 1,
                "domains": 1,
                "total": json_data['audits']['metrics']['numericValue'],
                "speed_index": json_data['audits']['metrics']['details']['items'][0]['speedIndex'],
                "time_to_first_byte": int(json_data['audits']['server-response-time']['numericValue']),
                "time_to_first_paint": json_data['audits']['metrics']['details']['items'][0]['observedFirstPaint'],
                "dom_content_loading": json_data['audits']['metrics']['details']['items'][0]['observedDomContentLoaded'],
                "dom_processing": json_data['audits']['metrics']['details']['items'][0]['observedDomContentLoaded'],  # TODO check dom_processing
                "first_contentful_paint": json_data['audits']['metrics']['details']['items'][0]['firstContentfulPaint'],
                "largest_contentful_paint": json_data['audits']['metrics']['details']['items'][0]['largestContentfulPaint'],
                "cumulative_layout_shift": round(float(json_data['audits']['metrics']['details']['items'][0]['cumulativeLayoutShift']), 3),
                "total_blocking_time": json_data['audits']['metrics']['details']['items'][0]['totalBlockingTime'],
                "first_visual_change": json_data['audits']['metrics']['details']['items'][0]['observedFirstVisualChange'],
                "last_visual_change": json_data['audits']['metrics']['details']['items'][0]['observedLastVisualChange']
            }

            data = {
                "name": json_data["requestedUrl"],
                "type": "page",
                "identifier": f"{json_data['requestedUrl']}@open",
                "metrics": result,
                "bucket_name": "reports",
                "file_name": file_name,
                "resolution": "auto",
                "browser_version": "chrome",
                "thresholds_total": thresholds.get("total", 0),
                "thresholds_failed": thresholds.get("failed", 0),
                "locators": [],
                "session_id": "session_id"
            }

            try:
                requests.post(f"{URL}/api/v1/observer/{PROJECT_ID}/{REPORT_ID}", json=data,
                              headers={'Authorization': f"Bearer {TOKEN}"})
            except Exception:
                print(format_exc())

            file = {'file': open(each["htmlPath"], 'rb')}

            try:
                requests.post(f"{URL}/api/v1/artifacts/{PROJECT_ID}/reports/{file_name}",
                              files=file,
                              headers={'Authorization': f"Bearer {TOKEN}"})
            except Exception:
                print(format_exc())

    time = datetime.now(tz=pytz.timezone("UTC"))
    report_data = {
        "report_id": REPORT_ID,
        "time": time.strftime('%Y-%m-%d %H:%M:%S'),
        "status": "Finished",
        "thresholds_total": thresholds.get("total", 0),
        "thresholds_failed": thresholds.get("failed", 0)
    }

    try:
        requests.put(f"{URL}/api/v1/observer/{PROJECT_ID}", json=report_data,
                     headers={'Authorization': f"Bearer {TOKEN}"})
    except Exception:
        print(format_exc())


except Exception:
    print(format_exc())
