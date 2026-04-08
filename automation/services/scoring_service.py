from __future__ import annotations

from automation.models.prospect import ProspectProfile


class ScoringService:
    FIRM_KEYWORDS = {
        "placement": 95,
        "capital advisory": 95,
        "advisory": 80,
        "private equity": 85,
        "pe": 70,
        "venture capital": 80,
        "vc": 75,
    }

    LEVEL_SCORES = {
        "high": 100,
        "medium": 65,
        "low": 30,
        None: 45,
    }

    def score(self, profile: ProspectProfile) -> ProspectProfile:
        firm_fit_score = self._firm_fit_score(profile.firm_type)
        signal_level = self._max_level(profile.outbound_need_level, profile.recent_signal_level)
        signal_score = self.LEVEL_SCORES.get(signal_level, 45)
        contact_coverage_score = self._contact_coverage_score(profile)
        confidence_score = self.LEVEL_SCORES.get(profile.data_confidence_level, 45)

        final_score = round(
            (firm_fit_score * 0.35)
            + (signal_score * 0.30)
            + (contact_coverage_score * 0.20)
            + (confidence_score * 0.15)
        )
        fit_bucket = "high" if final_score >= 70 else "medium" if final_score >= 45 else "low"

        reasons = []
        if firm_fit_score >= 85:
            reasons.append("strong ICP match")
        if signal_score >= 65:
            reasons.append("clear urgency signal")
        if contact_coverage_score >= 60:
            reasons.append("good contact coverage")
        if confidence_score < 45:
            reasons.append("research confidence is limited")

        profile.firm_fit_score = firm_fit_score
        profile.signal_score = signal_score
        profile.contact_coverage_score = contact_coverage_score
        profile.confidence_score = confidence_score
        profile.outbound_fit_score = final_score
        profile.outbound_fit_bucket = fit_bucket
        profile.outbound_fit_reason = ", ".join(reasons) if reasons else "mixed fit signals"
        return profile

    def _firm_fit_score(self, firm_type: str | None) -> int:
        if not firm_type:
            return 45
        lowered = firm_type.lower()
        for keyword, score in self.FIRM_KEYWORDS.items():
            if keyword in lowered:
                return score
        return 50

    def _contact_coverage_score(self, profile: ProspectProfile) -> int:
        if not profile.decision_makers:
            return 10
        score = min(len(profile.decision_makers), 3) * 20
        for person in profile.decision_makers[:3]:
            if person.email:
                score += 20
            elif person.linkedin_url:
                score += 10
        return min(score, 100)

    def _max_level(self, left: str | None, right: str | None) -> str | None:
        ordering = {"low": 0, "medium": 1, "high": 2}
        options = [value for value in (left, right) if value in ordering]
        if not options:
            return None
        return max(options, key=lambda value: ordering[value])
