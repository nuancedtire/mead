llm_config = {
    "small_model": "gpt-4o-mini",
    "large_model": "gpt-4o",
    "system_prompt": """You are a content strategist specializing in crafting engaging and informative social media posts for healthcare professionals based on detailed medical articles or web content. Your task is to create ready-to-use social media posts that accurately summarize key points in a way that is relevant and thought-provoking.

Guidelines:

- Engaging Openers: Begin with a creative hook that captures attention—use clinical scenarios, surprising statistics, or thought-provoking questions (avoiding overused phrases like "Did you know?").
- Informative Content: Offer a concise yet comprehensive summary of the most crucial information, ensuring it's clear and relevant to healthcare professionals.
- Balanced Tone: Keep a professional yet approachable tone. Use varied sentence structures and a conversational style that resonates with your audience.
- Highlight Key Findings: Utilize bullet points to present important statistics or findings, making the information easy to read and digest.
- Foster Engagement: End with a thoughtful question or statement that encourages reflection or invites interaction, ensuring it feels natural and appropriate.
- Emojis Usage: Use emojis sparingly and strategically to emphasize key points or statistics while maintaining professionalism.
- Formatting: Deliver the final post as plain text with line breaks, formatted for easy reading without the need for markdown or HTML.

Key Focus:

- Clarity and Comprehensiveness: Make sure the post covers essential details to effectively inform healthcare professionals.
- Readability: Enhance readability by using bullet points and varying sentence lengths.

Example Post:

---

⏱️ A once-weekly insulin matching daily doses—could this revolutionize type 2 diabetes management?

In the QWINT-2 phase 3 trial, once-weekly insulin efsitora alfa showed:

📊 A1C reduction of 1.34% compared to 1.26% with daily insulin degludec, resulting in A1C levels of 6.87% and 6.95% respectively at 52 weeks.

⏰ An extra 45 minutes in target glucose range per day without an increased risk of hypoglycemia.

🛡️ A safety profile comparable to daily insulins, with no severe hypoglycemic events reported for efsitora.

Could once-weekly dosing enhance adherence and lessen the treatment burden for your patients?""",
    "category": [
        "HealthTech & Startups",
        "Life Sciences & BioTech",
        "Research & Clinical Trials",
        "Healthcare & Policy"
    ],
    "hashtags": [
        "GeneralResearch",
        "ClinicalTrials",
        "MedicalDevices",
        "DigitalHealth",
        "Telemedicine",
        "HealthTech",
        "AIInHealthcare",
        "Cardiology",
        "Oncology",
        "Neurology",
        "Endocrinology",
        "InfectiousDiseases",
        "Pulmonology",
        "Rheumatology",
        "Gastroenterology",
        "Dermatology",
        "Hematology",
        "Nephrology",
        "Ophthalmology",
        "ENT",
        "Pediatrics",
        "Geriatrics",
        "Psychiatry",
        "Surgery",
        "Orthopedics",
        "Radiology",
        "Pathology",
        "Anesthesiology",
        "CriticalCare",
        "EmergencyMedicine",
        "PrimaryCare",
        "FamilyMedicine",
        "MedicalEthics",
        "HealthPolicy",
        "HealthcareRegulation",
        "Reimbursement",
        "CME",
        "MedicalEducation",
        "MedicalConferences",
        "MergersAcquisitions",
        "DrugDevelopment",
        "MarketTrends",
        "PatientSupport",
        "HealthEquity",
        "HealthAccess",
        "PublicHealth",
        "Genomics",
        "PersonalizedMedicine",
        "Biotechnology",
        "WearableTech",
        "mHealth",
        "RemoteMonitoring",
        "Telehealth",
        "HealthcareInnovation",
        "EHR",
        "PatientEngagement",
        "BigDataInHealth",
        "VRInHealthcare",
        "ARInHealthcare",
        "BlockchainInHealth",
        "CybersecurityInHealth",
        "HealthcareRobotics",
        "3DPrintingMedicine",
        "RegenerativeMedicine",
        "PrecisionMedicine",
        "MentalHealth",
        "SleepMedicine",
        "PalliativeCare",
        "PainManagement",
        "Nutrition",
        "LifestyleMedicine",
        "HealthEconomics",
        "PopulationHealth",
        "SocialDeterminantsOfHealth",
        "MedicalImaging",
        "VirtualCare",
        "HealthDataPrivacy",
        "HealthStartups",
        "HealthEntrepreneurship",
        "GlobalHealth",
        "DisasterMedicine",
        "TravelMedicine",
        "OccupationalHealth",
        "SportsMedicine",
        "IntegrativeMedicine",
        "AlternativeMedicine",
        "MedicalHistory",
        "HealthcareDesign",
        "HealthMarketing",
        "Pharmacovigilance",
        "HealthOutcomes",
        "MedicalStatistics",
        "PatientSafety",
        "SustainableHealth",
        "EnvironmentalHealth",
        "HealthSupplyChain",
        "HealthLiteracy",
        "PatientEducation"
    ]
}

# Image generation configuration
image_gen_config = {
    "model": "fal-ai/flux/dev",  # 'Schnell' focuses on speed; good for faster iterations
    "num_inference_steps": 40,  # Increase inference steps for better quality (8 is fast, but 12 gives a good balance)
    "image_size": "landscape_16_9",  # More standard widescreen aspect ratio for modern visuals
    "enable_safety_checker": True,  # Keep safety checks enabled, especially for public-facing or large datasets
    "guidance_scale": 6,  # Increase guidance scale for more creative control
}
