import os
from dotenv import load_dotenv
from groq import Groq

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")

if not GROQ_API_KEY:
    print("❌ Erreur: GROQ_API_KEY absente du fichier .env")
    exit(1)

client = Groq(api_key=GROQ_API_KEY)

try:
    print("🔍 Récupération des modèles accessibles avec ta clé Groq...")
    models = client.models.list()
    active_models = [m.id for m in models.data]
    
    print("\n✅ Modèles actifs disponibles sur ton compte :")
    for model_id in active_models:
        print(f" - {model_id}")

    # Choix automatique du premier modèle disponible
    target_model = active_models[0]
    print(f"\n🧪 Test d'une requête avec le modèle : {target_model}")

    chat_completion = client.chat.completions.create(
        messages=[{"role": "user", "content": "Dis 'CineMind fonctionne !'"}],
        model=target_model,
    )

    print(f"\nRésultat LLM : {chat_completion.choices[0].message.content}")

except Exception as e:
    print(f"\n❌ Erreur rencontrée : {e}")