# HTTP API

The hosted API runs the postkitty engine behind the [playground](https://postkitty.mertkayacs.com/try/). You send text, a photo or a video, and you get back the same checked files the plugin makes.

```text
https://postkitty.mertkayacs.com/api
```

It needs no key. Four things to know before you use it:

- **It has no language model.** It counts, checks and splits your text exactly as written, with the same rules as the plugin. Rewriting a draft for each platform is the job of the plugin inside Hermes.
- **Your files go to a hosted server.** Each job and its files are deleted 60 minutes after the job finishes, and `DELETE` removes them at once. The plugin does the same work on your own machine.
- **Uploads only.** The service never fetches a URL and never posts anywhere.
- **It is a small shared service.** For regular use, install the plugin or call the engine yourself ([Architecture](architecture.md#layers)).

## Endpoints

| Method | Path | What it does |
|---|---|---|
| `GET` | `/v1/health` | Says whether the service is up, with its version, the engine commit, the ffmpeg version, and whether captions and HDR video are supported. |
| `GET` | `/v1/limits` | The upload, queue and rate limits in force. |
| `GET` | `/v1/platforms` | Every platform and target with its size and limits, from `data/platforms.yaml`. |
| `POST` | `/v1/text` | Counts a text with each platform's rule and splits threads. |
| `POST` | `/v1/check` | Checks one file against one target. |
| `POST` | `/v1/jobs` | Starts a job: one photo or one video, with or without text. Answers `202`. |
| `GET` | `/v1/jobs/{id}` | The state of a job, its targets, texts and files. |
| `GET` | `/v1/jobs/{id}/files/{path}` | One output file. |
| `GET` | `/v1/jobs/{id}/download` | A zip of every ready file, with the review board. |
| `DELETE` | `/v1/jobs/{id}` | Deletes the job and its files now. A running job is stopped. |

The OpenAPI document is at `/openapi.json` under the same base URL.

## Count a text

`POST /v1/text` takes JSON.

| Field | Type | Default | Meaning |
|---|---|---|---|
| `text` | string | required | The post text. |
| `platforms` | list of strings | every platform | Platform names or target ids. |
| `split_threads` | boolean | `true` | Split text over the limit into a numbered thread on X, Threads and Bluesky. |

```sh
curl -s https://postkitty.mertkayacs.com/api/v1/text \
  -H 'Content-Type: application/json' \
  -d '{"text": "We shipped the app in one weekend.", "platforms": ["x", "bluesky"]}'
```

```json
{
  "all_ok": true,
  "platforms": {
    "x": {
      "label": "X", "ok": true, "enforcement": "hard", "unit": "x_weighted",
      "limit": 280, "count": 34, "overflow": 0, "split": false,
      "parts": [{"text": "We shipped the app in one weekend.", "count": 34}],
      "hashtags": 0, "mentions": 0, "urls": 0, "fold": null, "notes": []
    }
  }
}
```

`count` is the length of the longest part in the platform's own unit, and `overflow` says how far it is over the limit. `fold` is the part a feed shows before "more". The response has one entry per platform, and the example shows the first.

## Check a file

`POST /v1/check` takes a multipart form with `file` (one photo or video) and `target` (a target id from `/v1/platforms`, such as `tiktok` or `instagram_reel`).

```sh
curl -s https://postkitty.mertkayacs.com/api/v1/check -F 'file=@clip.mp4' -F 'target=tiktok'
```

```json
{"file": "clip.mp4", "kind": "video", "target": "tiktok", "pass": true, "checks": []}
```

`checks` lists every check that failed or carries advice, with the measured value, the expected value and the source of the limit.

## Make files

`POST /v1/jobs` takes a multipart form.

| Field | Meaning |
|---|---|
| `files` | One photo, or one video. Every target of a job is made from one file, so send one job per photo. |
| `captions` | An `.srt` or `.vtt` file in UTF-8, up to 1 MB, for a video job. The subtitles are burned into the video. |
| `text` | The post text. It is counted, checked and split. |
| `platforms` | Platform names or target ids, repeated or separated by commas. Leave it out for every platform that fits the files. |
| `layout` | `auto`, `crop`, `split`, `speaker`, `seam` or `pad`, for every media target ([Layouts](layouts.md)). |
| `focus` | `auto`, `left`, `center`, `right`, `person:N` or `x:0.0` to `x:1.0`, for every media target. |

The answer is `202` with the job `id`, its `status` and `links` to the status and the download. The links start with `/v1/`, so put the base URL in front of them. The id is the only key to the job, and there is no endpoint that lists jobs. Ask `GET /v1/jobs/{id}` every two seconds until `status` is `done` or `failed`.

```sh
curl -s https://postkitty.mertkayacs.com/api/v1/jobs \
  -F 'files=@team.jpg' \
  -F 'text=We shipped the app in one weekend.' \
  -F 'platforms=instagram,x'
```

The same in Python, from the upload to the zip:

```python
import time

import requests

API = "https://postkitty.mertkayacs.com/api"

with open("team.jpg", "rb") as photo:
    job = requests.post(
        f"{API}/v1/jobs",
        files={"files": photo},
        data={"text": "We shipped the app in one weekend.", "platforms": "instagram,x"},
    ).json()
if "error" in job:
    raise SystemExit(f"{job['error']['message']} {job['error']['hint']}")

while True:
    state = requests.get(f"{API}/v1/jobs/{job['id']}").json()
    if state["status"] in ("done", "failed"):
        break
    time.sleep(2)

for row in state["targets"]:
    print(row["id"], row["status"], row["file"])

with open("ready.zip", "wb") as out:
    out.write(requests.get(f"{API}/v1/jobs/{job['id']}/download").content)
```

What a job status holds:

| Key | Meaning |
|---|---|
| `status` | `queued`, `running`, `done` or `failed`. |
| `progress` | The current `stage`, a `note`, and the `position` in the queue while the job waits. |
| `targets` | One row per target: `status` (`ready`, `repaired`, `failed` or `skipped`), the `file` and its `url`, the `layout`, and the `problems`, `advisories` and `repairs`. |
| `text` | The count for each platform, in the shape of `/v1/text`. |
| `files` | Every ready file with its `path`, `url`, `platform`, `kind` and size. |
| `expires_at` | When the job and its files are deleted. |
| `error` | Set when the job failed. Its `code` is `job_failed` (the engine refused the input, and the message says why), `job_timeout` or `job_crashed`. |

Only targets with the status `ready` or `repaired` have a file.

## Limits

`GET /v1/limits` returns the values in force. These are the ones the service starts with:

| Limit | Value |
|---|---|
| Files in one job | One photo, or one video, and one caption file with a video |
| Photo | 20 MB and 50 megapixels at most. JPEG, PNG, WebP or still GIF. |
| Video | 80 MB, 120 seconds and 4,096 pixels on the longer side at most. MP4, MOV, MKV or WebM. |
| Text | 20,000 characters |
| Requests per hour | 12 jobs, 120 text and check requests, 3,600 reads |
| Waiting jobs | 8. A full queue answers `503`. |
| Files kept | 60 minutes after the job finishes |

Rates are counted per visitor. Browsers allow calls from the postkitty site only, so call the API from a script or a server.

The service sleeps when nobody uses it. The first request after a pause can be answered with a page that is not JSON, or with a `503`, while it starts. Ask `/v1/health` again until it answers.

## Errors

Every error has one shape:

```json
{"error": {"code": "video_too_long", "message": "One plain sentence that says what is wrong.", "hint": "What to do about it."}}
```

| Status | Codes | When |
|---|---|---|
| `400` | `invalid_text` | The engine could not count the text. |
| `403` | `origin_not_allowed` | A browser on another website made the request. |
| `404` | `not_found`, `job_not_found`, `file_not_found` | No such path. The job never existed, was deleted or has expired, or it has no file at that path. |
| `405` | `method_not_allowed` | The path does not take this method. |
| `409` | `job_not_ready` | A download was asked for before the job finished, or the job failed. |
| `413` | `upload_too_large`, `file_too_large` | The request or one file is over the size limit. |
| `415` | `unsupported_type` | The file is not a photo or video the service reads. |
| `422` | `invalid_request`, `empty_text`, `invalid_text`, `text_too_long`, `empty_job`, `too_many_files`, `unknown_platform`, `unknown_target`, `no_matching_target`, `wrong_media_kind`, `invalid_layout`, `invalid_focus`, `unreadable_file`, `animated_image`, `image_too_large`, `video_too_large`, `video_too_long`, `captions_need_video`, `captions_not_text`, `invalid_captions`, `check_failed` | Something in the request is wrong. The `message` names it. |
| `429` | `rate_limited` | Too many requests in the last hour. The `Retry-After` header says how long to wait. |
| `500` | `internal_error` | A fault on the server. |
| `501` | `captions_unavailable` | The service cannot burn captions in at the moment. |
| `503` | `queue_full`, `busy` | The queue is full or the service is busy. The `Retry-After` header says how long to wait. |
| `504` | `check_timeout` | A check did not finish in time and was stopped. |
