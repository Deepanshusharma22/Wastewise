# Project tracking (external resources)

| Resource | Identifier | Created |
|---|---|---|
| GitHub repo | `Madhurchaudhary/Wastewise` | pre-existing |
| Supabase project | ref `tfcwyccbhspkxfttfefc` (ap-south-1) | 2026-11-25 |
| Linear project | WasteWise (`12de8516-69e9-45ca-b64f-c9f9b6d3d45a`), team MAD | 2026-11-25 |
| Linear milestones | M1 Architecture & Setup … M8 Testing & Deployment | 2026-11-25 |
| Linear issues | MAD-5 … MAD-15 | 2026-11-25 |
| Google Drive | folder `WasteWise` (`1EYCcOmptzodLbSpiCTXmzLhnjoOSNnze`), with subfolders Research, Datasets, Dataset_Reports, Model_Experiments, Model_Evaluation, UI_Assets, Final_Documentation | 2026-11-25 |
| Google Sheets | `WasteWise Experiment Tracker` (`1CvQ8XTrT61L9n1nJNyr0TVkEv8C1JvMvazfoCnaawPw`) in Model_Experiments | 2026-11-25 |
| Vercel API | project `wastewise-api` (`prj_0RjA2En1WrbNJzZA5xvPRXIKHZEy`) at https://wastewise-api-three.vercel.app | 2026-11-25 |
| Vercel web | project `wastewise` (`prj_n8GUFaaBXo9wu5fRKBdGObN3J22g`) at https://wastewise-three-lilac.vercel.app | 2026-11-25 |
| Supabase `model_metrics` | 3 rows (one per experiment, test set `wastewise-v1-test`) | 2026-11-26 |
| Drive Model_Experiments | best checkpoints for exp01/exp02/exp03 | 2026-11-25 |
| Drive Model_Evaluation | `model_comparison.md`, confusion matrix, classification report, training curves, Grad-CAM sample of a user photo | 2026-11-26 |
| Drive Final_Documentation | Google Doc `WasteWise - Final Project Report` (converted from `docs/final_report.md`) | 2026-11-26 |
| Notion | page `WasteWise Knowledge Base` (`42320c33-b608-8137-a095-e729915b1add`) | 2026-11-25 |

Inspected on 2026-11-25 with nothing found to reuse: Google Drive (no WasteWise files), Notion (no WasteWise pages), Vercel (no projects).
Raw datasets are deliberately not copied to Drive, because of their licences and size; `ml/scripts/fetch_datasets.sh` rebuilds them. Every number in the tracker, Supabase, Notion and the report comes from `ml/reports/`, and the test set was evaluated once, after model selection.
