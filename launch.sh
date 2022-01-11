#!/bin/bash

args=$@
export reports=""
IFS=" " read -ra PARAMS <<< "$args"
for index in "${!PARAMS[@]}"
do
    if [[ ${PARAMS[index]} == "-tid" ]]; then
        test_id=${PARAMS[index + 1]}
    fi
    if [[ ${PARAMS[index]} == "-r" ]]; then
        reports=$reports";"${PARAMS[index + 1]}
    fi
done

python3 minio_tests_reader.py
echo "Scripts downloaded"
echo "Start test"
lhci autorun
echo "Test is done. Results processing..."
python3 results_processing.py $test_id $reports