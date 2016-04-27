#!/bin/bash
flake8 .
isort --recursive --check-only .
