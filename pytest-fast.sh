#!/bin/sh

# Este script invoca a pytest con todos las 'apps' de django pero evitando el largo collection time.

pytest $* \
	adjuntos \
	fiscales \
	api \
	elecciones \
	antitrolling \
	problemas \
	scheduling \
	contacto \
