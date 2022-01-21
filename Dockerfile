FROM python:3.7-buster

COPY requirements.txt /requirements.txt
RUN pip install -r /requirements.txt

RUN groupadd --gid 1000 appuser \
    && useradd --uid 1000 --gid appuser --shell /bin/bash --create-home appuser

USER appuser
ADD volatile /app/volatile

ENTRYPOINT ["python"]
CMD ["/app/volatile/volatile.py"]
