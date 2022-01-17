from util import is_threshold_failed, get_aggregated_value
from os import environ
from traceback import format_exc
import requests
from json import loads
from datetime import datetime
import pytz
import sys

PROJECT_ID = environ.get('GALLOPER_PROJECT_ID')
URL = environ.get('GALLOPER_URL')
REPORT_ID = environ.get('REPORT_ID')
BUCKET = environ.get("TESTS_BUCKET")
REPORTS_BUCKET = environ.get("REPORTS_BUCKET")
TEST = environ.get("ARTIFACT")
TOKEN = environ.get("token")
PATH_TO_FILE = f'/tmp/{TEST}'
TESTS_PATH = environ.get("tests_path", '/')
TEST_NAME = environ.get("JOB_NAME")


try:
    # Get thresholds
    res = None
    try:
        res = requests.get(
            f"{URL}/api/v1/thresholds/{PROJECT_ID}/ui?name={TEST_NAME}&environment=Default&order=asc",
            headers={'Authorization': f"Bearer {TOKEN}"})
    except Exception:
        print(format_exc())

    if not res or res.status_code != 200:
        thresholds = []

    try:
        thresholds = res.json()
    except ValueError:
        thresholds = []

    all_thresholds: list = list(filter(lambda _th: _th['scope'] == 'all', thresholds))
    every_thresholds: list = list(filter(lambda _th: _th['scope'] == 'every', thresholds))
    page_thresholds: list = list(filter(lambda _th: _th['scope'] != 'every' and _th['scope'] != 'all', thresholds))
    test_thresholds_total = 0
    test_thresholds_failed = 0
    # Read manifest.json
    with open("/manifest.json", "r") as f:
        manifest = loads(f.read())

    all_results = {"total": [], "speed_index": [], "time_to_first_byte": [], "time_to_first_paint": [],
                   "dom_content_loading": [], "dom_processing": [], "first_contentful_paint": [],
                   "largest_contentful_paint": [], "cumulative_layout_shift": [], "total_blocking_time": [],
                   "first_visual_change": [], "last_visual_change": []}

    # Read and process each page results json
    for each in manifest:
        json_path = each['jsonPath']
        with open(json_path, "r") as f:
            json_data = loads(f.read())
            page_thresholds_total = 0
            page_thresholds_failed = 0
            file_name = each["htmlPath"].split("/")[-1]
            result = {
                "requests": 1,
                "domains": 1,
                "total": json_data['audits']['metrics']['details']['items'][0]['observedLoad'],
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

            # Add page results to the summary dict
            for metric in list(all_results.keys()):
                all_results[metric].append(result[metric])

            # Process thresholds with scope = every
            for th in every_thresholds:
                test_thresholds_total += 1
                page_thresholds_total += 1
                if not is_threshold_failed(result.get(th["target"]), th["comparison"], th["metric"]):
                    print(f"Threshold: {th['scope']} {th['target']} {th['aggregation']} value {result.get(th['target'])}"
                          f" comply with rule {th['comparison']} {th['metric']} [PASSED]")
                else:
                    test_thresholds_failed += 1
                    page_thresholds_failed += 1
                    print(f"Threshold: {th['scope']} {th['target']} {th['aggregation']} value {result.get(th['target'])}"
                          f" violates rule {th['comparison']} {th['metric']} [FAILED]")

            # Process thresholds for current page
            for th in page_thresholds:
                if th["scope"] == f'{json_data["requestedUrl"]}@open':
                    test_thresholds_total += 1
                    page_thresholds_total += 1
                    if not is_threshold_failed(result.get(th["target"]), th["comparison"], th["metric"]):
                        print(f"Threshold: {th['name']} {th['scope']} {th['target']} {th['aggregation']} value {result.get(th['target'])}"
                              f" comply with rule {th['comparison']} {th['metric']} [PASSED]")
                    else:
                        test_thresholds_failed += 1
                        page_thresholds_failed += 1
                        print(f"Threshold: {th['name']} {th['scope']} {th['target']} {th['aggregation']} value {result.get(th['target'])}"
                              f" violates rule {th['comparison']} {th['metric']} [FAILED]")

            # Update report with page results
            data = {
                "name": json_data["requestedUrl"],
                "type": "page",
                "identifier": f"{json_data['requestedUrl']}@open",
                "metrics": result,
                "bucket_name": "reports",
                "file_name": file_name,
                "resolution": "auto",
                "browser_version": "chrome",
                "thresholds_total": page_thresholds_total,
                "thresholds_failed": page_thresholds_failed,
                "locators": [],
                "session_id": "session_id"
            }

            try:
                requests.post(f"{URL}/api/v1/observer/{PROJECT_ID}/{REPORT_ID}", json=data,
                              headers={'Authorization': f"Bearer {TOKEN}"})
            except Exception:
                print(format_exc())

            # Send html file with page results
            file = {'file': open(each["htmlPath"], 'rb')}

            try:
                requests.post(f"{URL}/api/v1/artifacts/{PROJECT_ID}/reports/{file_name}",
                              files=file,
                              headers={'Authorization': f"Bearer {TOKEN}"})
            except Exception:
                print(format_exc())

    # Process thresholds with scope = all
    for th in all_thresholds:
        test_thresholds_total += 1
        if not is_threshold_failed(get_aggregated_value(th["aggregation"], all_results.get(th["target"])),
                                   th["comparison"], th["metric"]):
            print(f"Threshold: {th['scope']} {th['target']} {th['aggregation']} value {all_results.get(th['target'])}"
                  f" comply with rule {th['comparison']} {th['metric']} [PASSED]")
        else:
            test_thresholds_failed += 1
            print(f"Threshold: {th['scope']} {th['target']} {th['aggregation']} value {all_results.get(th['target'])}"
                  f" violates rule {th['comparison']} {th['metric']} [FAILED]")

    # Finalize report
    time = datetime.now(tz=pytz.timezone("UTC"))
    exception_message = ""
    if test_thresholds_total:
        violated = round(float(test_thresholds_failed / test_thresholds_total) * 100, 2)
        print(f"Failed thresholds: {violated}")
        if violated > 30:
            exception_message = f"Failed thresholds rate more then {violated}%"
    report_data = {
        "report_id": REPORT_ID,
        "time": time.strftime('%Y-%m-%d %H:%M:%S'),
        "status": "Finished",
        "thresholds_total": test_thresholds_total,
        "thresholds_failed": test_thresholds_failed,
        "exception": exception_message
    }

    try:
        requests.put(f"{URL}/api/v1/observer/{PROJECT_ID}", json=report_data,
                     headers={'Authorization': f"Bearer {TOKEN}"})
    except Exception:
        print(format_exc())

    # Email notification
    if len(sys.argv) > 2 and "email" in sys.argv[2].split(";"):
        secrets_url = f"{URL}/api/v1/secrets/{PROJECT_ID}/"
        try:
            email_notification_id = requests.get(secrets_url + "email_notification_id",
                                                 headers={'Authorization': f'bearer {TOKEN}',
                                                          'Content-type': 'application/json'}
                                                 ).json()["secret"]
        except:
            email_notification_id = ""

        if email_notification_id:
            task_url = f"{URL}/api/v1/task/{PROJECT_ID}/{email_notification_id}"

            event = {
                "notification_type": "ui",
                "test_id": sys.argv[1],
                "report_id": REPORT_ID
            }

            res = requests.post(task_url, json=event, headers={'Authorization': f'bearer {TOKEN}',
                                                               'Content-type': 'application/json'})
            print(f"Email notification {res.text}")

except Exception:
    print(format_exc())
