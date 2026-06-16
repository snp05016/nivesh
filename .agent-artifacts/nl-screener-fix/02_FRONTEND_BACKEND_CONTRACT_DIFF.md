# Frontend/Backend Contract Diff

## Request Model
**Frontend (Swift)**
```swift
struct NLScreenerRequest: Codable {
    let query: String
}
```
**Backend (Pydantic)**
```python
class NLScreenerRequest(BaseModel):
    query: str
```
**Status:** ✅ PERFECT MATCH

## Response Model - The Envelope
**Frontend Expected (Swift)**
```swift
struct NLScreenerResponse: Codable {
    let parsedFilters: [String: String]? // <-- THE ISSUE
    let results: [NLScreenerResult]
    ...
}
```
**Backend Actual Output (Python Dict -> JSON)**
```json
{
  "parsed_filters": {
    "pe_max": 20,            // Output by LLM as Number
    "sector": "Banks"        // Output by LLM as String
  },
  "results": [ ... ]
}
```
**Status:** ❌ SEVERE MISMATCH
- The frontend expects every value inside `parsed_filters` to be a `String` (`[String: String]`).
- The backend passes through the LLM output dynamically. The LLM is instructed to output numerical filters (like `pe_max`, `roce_min`), and logically outputs them as JSON `Number` types.
- Swift's strongly-typed `JSONDecoder` fails instantly with `DecodingError.typeMismatch` when trying to parse a JSON Number into a Swift `String`.

## Response Model - Results Array
**Frontend Expected (Swift)**
```swift
struct NLScreenerResult: Codable, Identifiable {
    var id: String { ticker } // Computed, ignored by JSONDecoder unless custom init
    let ticker: String
    let company: String
    let score: Double
    let reason: String
    let sector: String?
}
```
**Backend Actual Output (Python Dict)**
```python
{
    "ticker": t,                             # str
    "company": info.get("shortName", t),     # str
    "score": round(score, 1),                # float (valid JSON Number -> Swift Double)
    "reason": reason,                        # str
    "sector": info.get("sector", "Unknown")  # str
}
```
**Status:** ✅ PERFECT MATCH
- All property names match.
- `score` is formatted safely as a float.
- `sector` handles nullability safely.
- No Swift decoding issues expected here.

## Error Envelopes
**Frontend Expected (Swift)**
- Evaluates `httpResponse.statusCode == 200`. If false, assumes `URLError(.badServerResponse)`.
**Backend Behavior**
- If an exception occurs, throws `HTTPException(status_code=500, detail=str(e))`.
**Status:** ⚠️ OK, BUT OPAQUE
- Swift catches the 500 error, but the `catch` block blindly outputs `error.localizedDescription`. This presents a generic network error rather than the backend's `detail` message, but it doesn't cause the "correct format" error.
