# syntax = edrevo/dockerfile-plus
INCLUDE+ twin-scada.Dockerfile

FROM scada-builder
CMD [ "npm", "test" ]
