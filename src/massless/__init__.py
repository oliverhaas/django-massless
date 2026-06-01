"""Drop-in, high-performance server and request pipeline for an unmodified Django
project: a Cython HTTP parse + uvloop transport feeds a lazy Django request through
Django's real URL resolver and middleware chain, deferring Django object
materialization until a handler touches it.
"""
