# AI Datasets (Demo)

Este directorio contiene datasets de referencia para clasificacion de incidentes vehiculares:

- `urgency_rules.json`: reglas por nivel de urgencia.
- `incident_categories.json`: categorias y palabras clave.
- `incident_examples.csv`: ejemplos etiquetados.
- `vehicle_symptoms_keywords.json`: sintomas y terminos asociados.

Uso sugerido:
- Cargar estos archivos desde `app/services/groq_urgency_service.py` para enriquecer prompts.
