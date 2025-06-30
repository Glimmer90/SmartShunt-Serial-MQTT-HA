ARG BUILD_FROM
FROM $BUILD_FROM

RUN apk add --no-cache \
    python3 \
    py3-pip \
    bash \
    && pip3 install --no-cache-dir paho-mqtt pyserial --break-system-packages

COPY smartshunt.py /smartshunt.py
COPY run.sh /run.sh

RUN chmod +x /run.sh

CMD ["/run.sh"]
