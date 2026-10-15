# Smart E-Commerce Order Support

A CrewAI and Streamlit demo that coordinates four agents to handle order questions:

1. **Customer Support Agent** verifies the order and classifies the issue.
2. **Inventory Agent** checks available stock and suggests the configured alternative.
3. **Delivery Agent** checks mock tracking status and the estimated delivery date.
4. **Resolution Agent** consolidates the findings, recommends an action, and decides whether human follow-up is needed.

The sample order database is `sample_orders.csv`. It includes a delayed shipment (`ORD1025`), a delivered order (`ORD1001`), an out-of-stock product (`ORD1002`), and a lost shipment (`ORD1003`).

## Run locally

Use Python 3.10 or newer:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Add your Ollama Cloud API key to `OLLAMA_API_KEY` in the existing `.env` file. The defaults use Ollama's OpenAI-compatible cloud endpoint and the `gpt-oss:20b-cloud` model. Set `OLLAMA_MODEL` to a model available to your Ollama account if you want to use a different one. If you are connecting to a local Ollama server instead, set `OLLAMA_BASE_URL=http://localhost:11434/v1` and use a locally available model; local Ollama does not require an API key.

Then launch:

```powershell
streamlit run app.py
```

The Streamlit form asks for an order ID and the customer's question. For example, try `ORD1025` and "My delivery was due yesterday. Can you check it?" Ollama Cloud calls require internet access and a valid Ollama API key.

## Human escalation

The Resolution Agent can escalate when it determines that a case needs a representative. The application also enforces escalation for explicit human requests, payment/fraud/legal/safety complaints, and shipments marked lost. This prevents those cases from receiving an automatic-only resolution even if the model misses a trigger. Escalation is displayed as a recommendation; this demo does not create a support ticket or contact a representative.

## Tests

Run the local data and escalation-policy tests with:

```powershell
pytest
```

These tests do not make model API calls. The CrewAI end-to-end flow needs the configured Ollama API key and a model available to your account.
