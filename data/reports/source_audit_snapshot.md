# Source Audit Snapshot

## Ingest Summary
- written_to_db: 13
- raw_threads: 5
- raw_reddit: 5
- raw_x: 1
- raw_official: 11

## Stored Complaint Rows By Source
- official: 2
- reddit: 5
- threads: 5
- x: 1

## threads
- sample_count: 5
- first_example: Unifi ni sampai 3 hari takde internet kat rumah ye. Complaint pun takde tindakan lg. Klu mintak bayar bil tu takleh lambat sikit terus potong

## reddit
- sample_count: 5
- first_example: Commuters On Kelana Jaya Line Can Expect Delays Rapid KL has advised commuters on the Kelana Jaya Line to expect delays and longer waiting times following technical issues involvin

## x
- sample_count: 1
- first_example: Kelewatan Tren: Laluan Kelana Jaya / Train Delays: Kelana Jaya Line. Perkhidmatan bas perantara ulang-alik percuma disediakan di antara Bangsar dan KL Gateway.

## official
- sample_count: 11
- first_example: Ampang Line - Normal Service

## Stored Complaint Rows By Category and Source
- telco_internet | official | 1
- telco_internet | reddit | 2
- telco_internet | threads | 1
- transport | official | 1
- transport | reddit | 3
- transport | threads | 4
- transport | x | 1

## Notes
- This snapshot distinguishes raw collection count from complaint rows that survive filtering.
- Official pages are grounding sources; they help verification but are not high-density complaint feeds.
- X now uses targeted public profile discovery plus exact status-page fetches for selected service accounts.
- Raw source counts can vary slightly between runs because public search and profile surfaces are live.

