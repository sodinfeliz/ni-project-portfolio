---
title: Online Booking Revamp
period: 2024 Q1–Q2
tags: [healthcare, MVP, data-driven decisions]
---

> Moved {{a clinic chain}}'s phone-only booking online. I used call-center data to convince leadership to ship a minimal version first; it launched in two months, and three months later about 40% of bookings were online and call volume had dropped by roughly 30%.

## Background & Problem

{{a clinic chain}} with a dozen branches took every booking by phone. The call center handled {{thousands of calls}} a month, and peak-hour waits ran several minutes. Patients' top complaints were "I can't get through" and "I can't see which slots are open."

## My Role

Product manager: I ran discovery, evaluated the options, and owned the launch plan, working with three engineers and one designer. The call-center lead was the key stakeholder.

## Key Decisions & Trade-offs

**Full system vs. minimal version**

- Option A: build a full booking system with scheduling, waitlists, and reminders (about six months).
- Option B: ship only "see slots and book," integrating with the existing scheduling system via API (about two months).

Leadership leaned toward A. I categorized the call-center logs and found that about 70% of calls were simply asking about availability, so the pain was in *finding* slots, not in scheduling. With the scheduling integration also the riskiest part, I made the case for B and for letting launch data decide what came next.

## Results & Measurement

- About 40% of all bookings moved online within three months of launch.
- Call volume dropped by roughly 30%.
- No-show rate didn't improve, since reminders weren't built yet; they shipped in [[TODO: reminder launch date]].

## Lessons

Define success metrics with stakeholders before development starts. We added them after launch and lost the first two weeks of data.

## Likely Interview Questions

- **Tell me about a time you pushed back on a stakeholder.** Key points: call-log data showing 70% of demand was availability lookups; framing B as "two months, then let the data decide" to lower the perceived risk.
- **How did you decide what to leave out of v1?** Key points: the waitlist depended on real-time scheduling data, the riskiest piece; validate that people book online at all first.
- **What would you do if adoption had been lower than expected?** Key points: read the funnel first (discoverability, slot supply, flow length) before deciding what to change.
