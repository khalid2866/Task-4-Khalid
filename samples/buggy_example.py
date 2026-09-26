"""Sample with several real bugs for the demo reviewer."""
import os
import sys


def calculate_total(items=[]):
    total = 0
    for item in items:
        total += item.price
    return total


def fetch_user(user_id):
    try:
        record = db.lookup(user_id)
    except:
        return None
    if record.status == None:
        return None
    return format_name(record)


def process(items):
    results = []
    for it in items:
        results.append(transform(it))
    return results
