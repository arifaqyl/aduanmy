# Source Audit Snapshot

## Ingest Summary
- written_to_db: 12
- raw_threads: 5
- raw_reddit: 3
- raw_x: 1
- raw_official: 9

## Stored Complaint Rows By Source
- official: 3
- reddit: 3
- threads: 5
- x: 1

## threads
- sample_count: 5
- first_example: Unifi ni sampai 3 hari takde internet kat rumah ye. Complaint pun takde tindakan lg. Klu mintak bayar bil tu takleh lambat sikit terus potong

## reddit
- sample_count: 3
- first_example: Commuters on the Kelana Jaya Line can expect delays.

## x
- sample_count: 1
- first_example: Kelewatan Tren: Laluan Kelana Jaya / Train Delays: Kelana Jaya Line. Perkhidmatan bas perantara ulang-alik percuma disediakan di antara Bangsar dan KL Gateway.

## official
- sample_count: 9
- first_example: Kemas Kini Laluan Ampang/Sri Petaling

## Stored Complaint Rows By Category and Source
- telco_internet | official | 1
- telco_internet | reddit | 2
- telco_internet | threads | 1
- transport | official | 2
- transport | reddit | 1
- transport | threads | 4
- transport | x | 1

## Notes
- This snapshot distinguishes raw collection count from complaint rows that survive filtering.
- Official pages are grounding sources; they help verification but are not high-density complaint feeds.
- X now uses targeted public profile discovery plus exact status-page fetches for selected service accounts.
- Raw source counts can vary slightly between runs because public search and profile surfaces are live.

