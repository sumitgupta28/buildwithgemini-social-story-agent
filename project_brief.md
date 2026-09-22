# My agent: Personalized Cartoon Social Story Agent

One-liner: An assistive AI companion that creates visual, step-by-step social stories with customized family characters and cartoon avatars to help children with special needs navigate daily routines and transitions.

## Tool Coverage & Architecture
- **Memory**: Child's profile (Name: Aarav, Mother: Yamini, Father, Teacher, Friends), sensory triggers, comfort items, and past story history across sessions.
- **Firestore Database**: `manage_family_profile` (store/retrieve family character details) and `save_social_story` (persist generated stories for replay).
- **Image Generation (`gemini-3.1-flash-lite-image`)**: `generate_cartoon_illustration` (creates consistent 2D cartoon storybook scenes featuring the child's cartoon avatar and saves public HTTPS links to Google Cloud Storage).
- **Vertex AI RAG Engine**: `consult_ot_guidance` (retrieves grounded low-anxiety transition strategies from pediatric occupational therapy / SLP guides).
- **Sandbox Code Executor**: `calculate_routine_timer` (computes visual step countdowns and token economy reward tallies).
- **Adaptive UI (A2UI v0.8)**: Renders step-by-step story cards featuring cartoon illustrations, step titles, narrative text, and emotion check-in reaction tiles (`[😊 Ready!]`, `[😐 A little nervous]`).

## First Eval Question
"Create a 3-step social story for 6-year-old Aarav going to the dentist with his mother Yamini, including a cartoon illustration of Aarav sitting in the dentist chair with Mom Yamini standing beside him."
