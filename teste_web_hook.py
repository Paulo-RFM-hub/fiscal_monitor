import requests

url = "https://default62b87257cf3d47a6a3a76133a558f8.b0.environment.api.powerplatform.com/powerautomate/automations/direct/workflows/4af75a840e294302a96af0892394df48/triggers/manual/paths/invoke?api-version=1&sp=%2Ftriggers%2Fmanual%2Frun&sv=1.0&sig=F8Nzu8NmEN4Ll3U-5lCpWwbkWMyIDR79oz-fWwe3G9A"

payload = {
    "text": "✅ Teste Power Automate funcionando!"
}

response = requests.post(url, json=payload)

print("Status:", response.status_code)
print("Resposta:", response.text)