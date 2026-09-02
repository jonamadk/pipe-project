DOC_META = {
    "singh2020": {
        "title": "Managing Water Quality in Premise Plumbing",
        "meta": "Singh et al., 2020 — Water journal · 17 pages · SME interviews vs. 15 guidance documents",
    },
    "singh2022": {
        "title": "Practitioners' Perspective on Legionella Control",
        "meta": "Singh et al., 2022 — Water journal · 19 pages · Survey of 41 facility managers",
    },
}

SAMPLE_QUESTIONS = [
    "What temperature should my water heater be set to?",
    "Could PVC pipe be contributing to Legionella risk?",
    "What is the recommended flushing frequency for low-flow fixtures?",
    "Is there a conflict between scald safety and Legionella control?",
]

# The 18-question intake form from PIPE's public decision-support tool
# (Plumbing Information and Performance Evaluation), reproduced verbatim so
# the frontend form and the backend assessment prompt stay in sync.
ASSESSMENT_QUESTIONS = [
    {
        "id": "q1",
        "section": "Building Plumbing System Monitoring",
        "text": "Does your building have thermostatic mixing valves?",
        "options": ["Yes", "No", "Don't Know"],
    },
    {
        "id": "q1a",
        "section": "Building Plumbing System Monitoring",
        "text": "Is the thermostatic mixing valve centralized or are separate valves provided for individual fixtures?",
        "options": ["Individual", "Centralized"],
        "dependsOn": {"id": "q1", "value": "Yes"},
    },
    {
        "id": "q2",
        "section": "Building Plumbing System Monitoring",
        "text": (
            "What is the hot water temperature at a typical tap in your building? "
            "(i.e., when only the hot-water tap is open and the cold-water tap is completely "
            "closed and the faucet is running for a sufficiently long time, i.e. hot-water "
            "temperature is stabilized)"
        ),
        "options": [
            "> 140 °F [ > 60 °C ]",
            "131 - 139 °F [ 55 - 59 °C ]",
            "123 - 130 °F [ 51 – 54 °C ]",
            "119 - 122 °F [ 49 – 50 °C ]",
            "110 - 118 °F [ 43 – 48 °C ]",
            "< 110 °F [ < 43 °C ]",
            "Don't Know",
        ],
    },
    {
        "id": "q3",
        "section": "Building Plumbing System Monitoring",
        "text": (
            "How long does it take for the hot-water to reach a steady temperature from the "
            "time when the hot-water valve at a typical faucet is opened at its full capacity "
            "to the point when hot-water temperature stabilizes? (Note: Keep the cold-water "
            "valve closed for the entire duration)"
        ),
        "options": ["> 60 seconds", "31 – 60 seconds", "11 – 30 seconds", "1 – 10 seconds", "Don't know"],
    },
    {
        "id": "q4",
        "section": "Building Plumbing System Monitoring",
        "text": "Does your building have recirculation loop?",
        "options": ["Yes", "No"],
    },
    {
        "id": "q4a",
        "section": "Building Plumbing System Monitoring",
        "text": "What is the hot water temperature at the end of recirculation loop?",
        "options": [
            "≥ 140 °F [ ≥ 60 °C ]",
            "131 - 139 °F [ 55 - 59 °C ]",
            "123 - 130 °F [ 51 – 54 °C ]",
            "119 - 122 °F [ 49 – 50 °C ]",
            "110 - 118 °F [ 43 – 48 °C ]",
            "< 110 °F [ < 43 °C ]",
            "Don't Know",
        ],
        "dependsOn": {"id": "q4", "value": "Yes"},
    },
    {
        "id": "q5",
        "section": "Building Plumbing System Monitoring",
        "text": "What type of residual disinfectant is present in the plumbing system?",
        "options": ["Chlorine", "Monochloramine", "Chlorine Dioxide", "None"],
    },
    {
        "id": "q5a",
        "section": "Building Plumbing System Monitoring",
        "text": "What is the measured chlorine disinfectant residual level (mg/L) at a typical faucet in your plumbing system?",
        "options": ["< 0.2 mg/L", "0.2 – 0.5 mg/L", "0.6 – 0.9 mg/L", "1.0 – 2.0 mg/L", "> 2.0 mg/L", "Don't know"],
        "dependsOn": {"id": "q5", "value": "Chlorine"},
    },
    {
        "id": "q5b",
        "section": "Building Plumbing System Monitoring",
        "text": "What is the measured chloramine disinfectant residual level (mg/L) at a typical faucet in your plumbing system?",
        "options": ["< 0.5 mg/L", "0.5 – 2.0 mg/L", "2.0 – 4.0 mg/L", "> 4.0 mg/L", "Don't know"],
        "dependsOn": {"id": "q5", "value": "Monochloramine"},
    },
    {
        "id": "q5c",
        "section": "Building Plumbing System Monitoring",
        "text": "What is the measured chlorine dioxide disinfectant residual level (mg/L) at a typical faucet in your plumbing system?",
        "options": ["< 0.2 mg/L", "0.2 – 0.5 mg/L", "0.5 – 0.8 mg/L", "> 0.8 mg/L", "Don't know"],
        "dependsOn": {"id": "q5", "value": "Chlorine Dioxide"},
    },
    {
        "id": "q6",
        "section": "Building Plumbing System Monitoring",
        "text": "What is the water heater temperature setpoint in your building?",
        "options": [
            "≥ 140 °F [ ≥ 60 °C]",
            "131 – 139 °F [ 55 – 59 °C]",
            "123 – 130 °F [ 51 – 54 °C ]",
            "119 – 122 °F [49 – 50 °C ]",
            "110 – 118 °F [ 43 – 48 °C ]",
            "< 110 °F [ < 43 °C ]",
            "Don't Know",
        ],
    },
    {
        "id": "q7",
        "section": "General Water Devices",
        "text": (
            "Does your building have dead ends? (Dead ends - sections of pipes that do not "
            "have outlets at the end. Pipes that were capped either due to the removal of "
            "something or in anticipation of installing something at a later time.)"
        ),
        "options": ["Yes", "No"],
    },
    {
        "id": "q8",
        "section": "General Water Devices",
        "text": (
            "Does your building have low flow fixtures? (As per EPA, guidelines for low flow "
            "fixtures are: Shower heads - 2.0 gpm, Faucets - 1.5 gpm, Toilet - 1.28 gpf.)"
        ),
        "options": ["Yes", "No"],
    },
    {
        "id": "q9",
        "section": "General Water Devices",
        "text": "Does your building have Electronic (i.e., automatic/no touch) faucets?",
        "options": ["Yes", "No"],
    },
    {
        "id": "q10",
        "section": "General Water Devices",
        "text": "Does your building have Showers with flexible hoses?",
        "options": ["Yes", "No"],
    },
    {
        "id": "q11",
        "section": "Critical Water Devices",
        "text": "Does your building have a cooling tower?",
        "options": ["Yes", "No"],
    },
    {
        "id": "q12",
        "section": "Critical Water Devices",
        "text": "Does your building have a hot tub (also known as a spa) that is not drained between each use?",
        "options": ["Yes", "No"],
    },
    {
        "id": "q13",
        "section": "Critical Water Devices",
        "text": "Does your building have a decorative fountain?",
        "options": ["Yes", "No"],
    },
    {
        "id": "q14",
        "section": "Critical Water Devices",
        "text": "Does your building have a centrally-installed mister, atomizer, air washer, or humidifier?",
        "options": ["Yes", "No"],
    },
    {
        "id": "q15",
        "section": "Building/Facility Type",
        "text": (
            "Is your building a healthcare facility where patients stay overnight or does your "
            "building house or treat people who have chronic and acute medical problems or "
            "weakened immune systems?"
        ),
        "options": ["Yes", "No"],
    },
    {
        "id": "q16",
        "section": "Building/Facility Type",
        "text": "Does your building primarily house people older than 65 years (like a retirement home or assisted-living facility)?",
        "options": ["Yes", "No"],
    },
    {
        "id": "q17",
        "section": "Building/Facility Type",
        "text": "Does your building have multiple housing units and a centralized hot water system (like a hotel or high-rise apartment complex)?",
        "options": ["Yes", "No"],
    },
    {
        "id": "q18",
        "section": "Building/Facility Type",
        "text": "Does your building have more than 10 stories (including basement levels)?",
        "options": ["Yes", "No"],
    },
]

# Questions whose answer maps to an exact, pre-cited parameter in
# data/structured_facts.json, so the assessment can ground that specific
# answer in the same records the "structured" chat retrieval mode uses.
QUESTION_TO_STRUCTURED_PARAM = {
    "q2": "pou_temperature",
    "q3": "time_to_tap",
    "q4a": "recirculation_loop_temp",
    "q5a": "residual_disinfectant",  # chlorine residual level — the structured guidance is chlorine-specific
    "q6": "water_heater_setpoint",
}
