#!/bin/bash

exec uvicorn app:app --host 0.0.0.0 --port 8000 --timeout-keep-alive 1
