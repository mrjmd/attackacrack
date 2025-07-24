import google.generativeai as genai
from flask import current_app
import json

class AIService:
    def __init__(self):
        """
        Initializes the AI service without configuring the model immediately.
        The model will be configured on the first use.
        """
        self.model = None

    def _configure_model(self):
        """
        A helper method to configure the Gemini model just-in-time.
        This ensures the app context is available.
        """
        if self.model is None:
            try:
                api_key = current_app.config.get('GEMINI_API_KEY')
                if not api_key:
                    raise ValueError("GEMINI_API_KEY not found in configuration.")
                genai.configure(api_key=api_key)
                self.model = genai.GenerativeModel('gemini-1.5-flash')
                print("--- AIService model configured successfully ---")
            except Exception as e:
                print(f"Error initializing AIService model: {e}")
                self.model = False

    def extract_address_from_text(self, text: str) -> str | None:
        """
        Uses the Gemini API to extract and standardize a physical address from a text message.
        Returns the standardized address as a string, or None if not found.
        """
        self._configure_model()

        if not self.model or not text:
            return None

        prompt = f"""
        You are an address standardization assistant for a business that operates primarily in the greater Boston, Massachusetts area.
        Analyze the following text message to see if it contains a physical street address.
        If a partial or complete address is found, complete it to a full, standardized US address format including street name, city, state, and zip code.
        Use your knowledge of the Boston, MA area (including surrounding cities like Cambridge, Somerville, Brookline, etc.) to help complete partial or ambiguous addresses.
        If no address can be reasonably identified in the text, return ONLY the word "None".

        Examples:
        - Text: "Hi, I need a quote for 123 Beacon St in Boston" -> "123 Beacon St, Boston, MA 02116"
        - Text: "My house is at 700 mass ave cambridge" -> "700 Massachusetts Ave, Cambridge, MA 02139"
        - Text: "Can you come by 200 Highland Ave in Somerville?" -> "200 Highland Ave, Somerville, MA 02143"
        - Text: "Can you come by later today?" -> "None"

        Text to analyze: "{text}"
        """

        try:
            response = self.model.generate_content(prompt)
            extracted_text = response.text.strip()
            
            if "none" in extracted_text.lower():
                return None
            return extracted_text
            
        except Exception as e:
            print(f"Error calling Gemini API for address parsing: {e}")
            return None

    # --- NEW METHOD FOR NAME DETECTION ---
    def extract_name_from_text(self, text: str) -> tuple[str | None, str | None]:
        """
        Uses the Gemini API to extract a person's name from a text message.
        Returns a tuple of (first_name, last_name).
        """
        self._configure_model()

        if not self.model or not text:
            return None, None

        prompt = f"""
        Analyze the following text message to see if it contains a person's name.
        The name might be introduced with phrases like "My name is", "This is", or it might just be signed at the end.
        If a name is found, return a JSON object with "first_name" and "last_name" keys.
        If no name is found, return a JSON object with "first_name" and "last_name" keys set to null.

        Examples:
        - Text: "Hi, my name is John Doe and I need a quote." -> {{"first_name": "John", "last_name": "Doe"}}
        - Text: "This is Jane, I have a question." -> {{"first_name": "Jane", "last_name": null}}
        - Text: "I need a quote for my foundation. -Bob Smith" -> {{"first_name": "Bob", "last_name": "Smith"}}
        - Text: "Can you come by later today?" -> {{"first_name": null, "last_name": null}}

        Text to analyze: "{text}"
        """

        try:
            response = self.model.generate_content(prompt)
            # Clean up the response to ensure it's valid JSON
            cleaned_response = response.text.strip().replace("```json", "").replace("```", "")
            name_data = json.loads(cleaned_response)
            
            first_name = name_data.get("first_name")
            last_name = name_data.get("last_name")

            return first_name, last_name
            
        except Exception as e:
            print(f"Error calling Gemini API for name parsing: {e}")
            return None, None
    # --- END NEW METHOD ---
