/**
 * Shared profile and appearance preferences.
 * Uses localStorage so the static frontend works without a user backend.
 */

const MACROPULSE_PREFS_KEY = "macropulsePreferences";

const DEFAULT_PREFERENCES = {
    theme: "dark",
    signedIn: false,
    name: "",
    email: "",
    profileImage: "",
    priceAlerts: true,
    dailySummary: false,
    signalAlerts: true,
    weeklyDigest: false,
};

function getPreferences() {
    try {
        return {
            ...DEFAULT_PREFERENCES,
            ...JSON.parse(localStorage.getItem(MACROPULSE_PREFS_KEY) || "{}"),
        };
    } catch {
        return { ...DEFAULT_PREFERENCES };
    }
}

function savePreferences(updates) {
    const nextPreferences = {
        ...getPreferences(),
        ...updates,
    };

    localStorage.setItem(MACROPULSE_PREFS_KEY, JSON.stringify(nextPreferences));
    applyPreferences(nextPreferences);
    window.dispatchEvent(new CustomEvent("macropulsePreferencesChanged", { detail: nextPreferences }));
    return nextPreferences;
}

function resetPreferences() {
    localStorage.removeItem(MACROPULSE_PREFS_KEY);
    const nextPreferences = { ...DEFAULT_PREFERENCES };

    applyPreferences(nextPreferences);
    window.dispatchEvent(new CustomEvent("macropulsePreferencesChanged", { detail: nextPreferences }));
    return nextPreferences;
}

function applyPreferences(preferences = getPreferences()) {
    document.documentElement.setAttribute("data-theme", preferences.theme);
    updateProfileButton(preferences);
}

function getProfileInitials(preferences) {
    const source = preferences.name || preferences.email || "Guest";
    return source
        .trim()
        .split(/\s+/)
        .slice(0, 2)
        .map((part) => part.charAt(0).toUpperCase())
        .join("");
}

function updateProfileButton(preferences) {
    const profileButton = document.querySelector("[data-profile-button]");
    if (!profileButton) return;

    const profileImage = profileButton.querySelector("[data-profile-image]");
    const profileInitials = profileButton.querySelector("[data-profile-initials]");
    const statusText = profileButton.querySelector("[data-profile-status]");

    if (profileImage && profileInitials) {
        if (preferences.profileImage) {
            profileImage.src = preferences.profileImage;
            profileImage.hidden = false;
            profileInitials.hidden = true;
        } else {
            profileImage.removeAttribute("src");
            profileImage.hidden = true;
            profileInitials.hidden = false;
            profileInitials.textContent = getProfileInitials(preferences);
        }
    }

    if (statusText) {
        statusText.textContent = preferences.signedIn
            ? preferences.name || "Profile"
            : "Sign in";
    }
}

document.addEventListener("DOMContentLoaded", () => {
    applyPreferences();
});
