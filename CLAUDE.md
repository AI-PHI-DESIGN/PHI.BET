# Instrucciones para Claude

Antes de trabajar en este repo, lee `docs/PLAYBOOK.md`: describe cómo se construye el
proyecto (stack, estructura, pasos, verificación y convenciones). Sigue esos pasos igual
cada vez, y **actualiza el playbook** cuando se añada o cambie una forma de hacer las cosas.

- **La app es de análisis deportivo, no para apostar.** Nada de cuotas, apuestas, stakes ni
  dinero. Si algo empuja en esa dirección, pregunta antes.
- Idioma: español (nombres de código en inglés; comentarios, docs y UI en español).
- Colores de la marca: morado y negro (detalle en el playbook, sección Convenciones).
- Verificar siempre: `cd backend && ../.venv/bin/python -m pytest -q` y una captura de la web.
- Rama de trabajo: la que indique la sesión; no crear PR salvo que se pida.
