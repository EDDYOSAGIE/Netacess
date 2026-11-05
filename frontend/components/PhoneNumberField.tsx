"use client";
import { useMemo } from "react";
import { useEffect, useState } from "react";
import {
  getCountries,
  getCountryCallingCode,
  parsePhoneNumberFromString,
  type CountryCode,
} from "libphonenumber-js";

const regionNames = new Intl.DisplayNames(["en"], { type: "region" });
const countries = getCountries()
  .map((country) => ({
    code: country,
    name: regionNames.of(country) || country,
    callingCode: getCountryCallingCode(country),
  }))
  .sort((a, b) => a.name.localeCompare(b.name));

export function toE164PhoneNumber(value: string, country: CountryCode): string | null {
  const parsed = parsePhoneNumberFromString(value.trim(), country);
  return parsed?.isValid() ? parsed.number : null;
}

type PhoneNumberFieldProps = {
  value: string;
  country: CountryCode;
  onValueChange: (value: string) => void;
  onCountryChange: (country: CountryCode) => void;
};

export function PhoneNumberField({ value, country, onValueChange, onCountryChange }: PhoneNumberFieldProps) {
  const callingCode = useMemo(() => getCountryCallingCode(country), [country]);
  const [countryOptions, setCountryOptions] = useState<typeof countries>([]);

  useEffect(() => setCountryOptions(countries), []);

  function changePhone(input: string) {
    const parsed = input.trim().startsWith("+") ? parsePhoneNumberFromString(input) : undefined;
    if (parsed?.country) {
      onCountryChange(parsed.country);
      onValueChange(parsed.nationalNumber);
      return;
    }
    onValueChange(input);
  }

  return (
    <div className="phone-entry">
      <select
        aria-label="Country calling code"
        value={country}
        onChange={(event) => onCountryChange(event.target.value as CountryCode)}
      >
        {countryOptions.length === 0 && <option value={country}>+{callingCode}</option>}
        {countryOptions.map((item) => (
          <option key={item.code} value={item.code}>
            {item.name} (+{item.callingCode})
          </option>
        ))}
      </select>
      <div className="phone-input-wrap">
        <span aria-hidden="true">+{callingCode}</span>
        <input
          id="p"
          type="tel"
          required
          autoComplete="tel-national"
          inputMode="tel"
          placeholder="Phone number"
          value={value}
          onChange={(event) => changePhone(event.target.value)}
        />
      </div>
    </div>
  );
}