#!/bin/bash

DEV_TESTS="/Volumes/public/exchange/dabakumov/Sample Tests"

svn update "$DEV_TESTS"

#echo ${#TESTS[@]}

TESTS=("${TESTS[@]}" "$DEV_TESTS/HTTP(S) core dev tests/HTTP reconnect")

TESTS=("${TESTS[@]}" "$DEV_TESTS/HTTP(S) Auth/HTTP auth Basic Passive")
TESTS=("${TESTS[@]}" "$DEV_TESTS/HTTP(S) Auth/HTTP auth Basic Preemptive")
TESTS=("${TESTS[@]}" "$DEV_TESTS/HTTP(S) Auth/HTTP auth Digest Passive")

TESTS=("${TESTS[@]}" "$DEV_TESTS/HTTP(S) Auth/HTTP auth Digest Preemptive")
TESTS=("${TESTS[@]}" "$DEV_TESTS/HTTP(S) Auth/HTTP auth File Not Found")
TESTS=("${TESTS[@]}" "$DEV_TESTS/HTTP(S) Auth/HTTP auth Negotiate_NTLM IPv6")
TESTS=("${TESTS[@]}" "$DEV_TESTS/HTTP(S) Auth/HTTP auth NTLM")
TESTS=("${TESTS[@]}" "$DEV_TESTS/HTTP(S) Auth/HTTP negative Auth")

TESTS=("${TESTS[@]}" "$DEV_TESTS/HTTP(S) Redirect/HTTP DNS Redirect")
TESTS=("${TESTS[@]}" "$DEV_TESTS/HTTP(S) core dev tests/HTTP close by peer")

TESTS=("${TESTS[@]}" "$DEV_TESTS/HTTP(S) core dev tests/HTTP Expect100 with Encoding")
TESTS=("${TESTS[@]}" "$DEV_TESTS/HTTP(S) core dev tests/HTTP Expect100 with DV and Auth")
TESTS=("${TESTS[@]}" "$DEV_TESTS/HTTP(S) core dev tests/HTTP GET 10 files pipelined")

#TESTS=("${TESTS[@]}" "$DEV_TESTS/Object Storage/OpenStack Cinder/OpenStack Cinder All Commands")
TESTS=("${TESTS[@]}" "$DEV_TESTS/Object Storage/Amazon S3/Amazon S3 Client test - Object Operations")
#TESTS=("${TESTS[@]}" "$DEV_TESTS/Object Storage/Amazon S3/Amazon S3 POST Object")
#TESTS=("${TESTS[@]}" "$DEV_TESTS/Object Storage/Amazon S3/s3 multipart upload dev test")

#echo ${#TESTS[@]}

echo ./tac.py -v "${TESTS[@]}"
./tac.py -v "${TESTS[@]}"

#j=1
#for i in "${TESTS[@]}" 
#do
#    echo $j\) $i
#    j=$(($j+1))
#done
