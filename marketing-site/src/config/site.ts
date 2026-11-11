/**
 * Central business metadata, contact details, marketing claims, and SEO configuration.
 *
 * RULES:
 * 1. Nothing is hardcoded in page templates; all claims and business info originate here.
 * 2. In production builds, no placeholder strings, example.com, or localhost are permitted.
 * 3. Marketing claims MUST be factual:
 *    - NO PSARA / security guard services.
 *    - NO police verification claim (use KYC/identity verification).
 *    - NO "replacement guarantee" wording (use supervisor-managed replacement workflow).
 *    - NO invented statistics, client names, or awards.
 */

export interface AddressConfig {
  streetAddress: string;
  addressLocality: string;
  addressRegion: string;
  postalCode: string;
  addressCountry: string;
}

export interface SiteConfig {
  name: string;
  legalName: string;
  tagline: string;
  description: string;
  url: string;
  appUrl: string;
  email: string;
  phone: string;
  phoneFormatted: string;
  openingHours: string;
  serviceAreas: string[];
  address: AddressConfig;
  socialLinks: {
    sameAs: string[]; // Stays empty [] until real profiles exist
  };
  claims: {
    serviceScope: string;
    staffVerification: string;
    attendanceTracking: string;
    taskVerification: string;
    replacementWorkflow: string;
    qualityAssurance: string;
    psaraExclusionDisclaimer: string;
  };
  navigation: {
    links: Array<{ name: string; href: string }>;
  };
}

export const siteConfig: SiteConfig = {
  name: 'Altsan',
  legalName: 'Altsan Facility Services Private Limited',
  tagline: 'Managed Facility Staffing & Housekeeping Operations',
  description:
    'Dedicated, verified housekeeping staff deployed to residential societies, hospitals, and commercial facilities with geofenced attendance, photo checklists, and supervisor inspections.',
  url: 'https://altsan.com',
  appUrl: 'https://frontend-web-plum-ten.vercel.app',
  email: 'inquiries@altsan.com',
  phone: '+912067000000',
  phoneFormatted: '+91 (020) 6700-0000',
  openingHours: 'Mo-Sa 08:00-18:00',
  serviceAreas: ['Pune', 'Pimpri-Chinchwad'],
  address: {
    streetAddress: 'Main Road, Baner',
    addressLocality: 'Pune',
    addressRegion: 'Maharashtra',
    postalCode: '411045',
    addressCountry: 'IN',
  },
  socialLinks: {
    sameAs: [], // Stays empty until real social profiles are verified
  },
  claims: {
    serviceScope:
      'Professional housekeeping, common-area sanitation, and allied facility maintenance.',
    staffVerification:
      'Structured onboarding with government ID verification, KYC documentation, and background screening.',
    attendanceTracking:
      'Mobile geofenced attendance validating worker clock-in within premises boundaries.',
    taskVerification:
      'Photo-verified cleaning checklists and regular supervisor quality inspections.',
    replacementWorkflow:
      'Supervisor-coordinated reliever assignment workflow to cover planned leaves and unexpected absences.',
    qualityAssurance:
      'Monthly operational performance reports and resident complaint resolution tracking.',
    psaraExclusionDisclaimer:
      'Altsan provides housekeeping and facility upkeep services only. We do not provide private security guards or PSARA-licensed security services.',
  },
  navigation: {
    links: [
      { name: 'Services', href: '/housekeeping' },
      { name: 'How It Works', href: '/how-it-works' },
      { name: 'For Societies', href: '/for-societies' },
      { name: 'About', href: '/about' },
      { name: 'FAQ', href: '/faq' },
      { name: 'Contact', href: '/contact' },
    ],
  },
};

/**
 * Checks whether address and service areas are real and filled out,
 * to determine whether LocalBusiness JSON-LD can be legally and cleanly emitted.
 */
export function hasRealAddress(config: SiteConfig): boolean {
  const addr = config.address;
  if (!addr) return false;
  return Boolean(
    addr.streetAddress &&
      addr.addressLocality &&
      addr.addressRegion &&
      addr.postalCode &&
      addr.addressCountry &&
      !addr.streetAddress.includes('placeholder')
  );
}

export function hasRealServiceArea(config: SiteConfig): boolean {
  return Array.isArray(config.serviceAreas) && config.serviceAreas.length > 0;
}

/**
 * Production validation function.
 * Fails if any required value is empty, placeholder, localhost, or example.com.
 */
export function validateSiteConfig(config: SiteConfig, isProduction: boolean): string[] {
  const errors: string[] = [];

  const requiredFields: Array<{ key: string; val: unknown }> = [
    { key: 'name', val: config.name },
    { key: 'legalName', val: config.legalName },
    { key: 'url', val: config.url },
    { key: 'appUrl', val: config.appUrl },
    { key: 'email', val: config.email },
    { key: 'phone', val: config.phone },
    { key: 'description', val: config.description },
  ];

  for (const { key, val } of requiredFields) {
    if (!val || typeof val !== 'string' || val.trim().length === 0) {
      errors.push(`siteConfig.${key} is required and cannot be empty.`);
    }
  }

  const disallowedTokens = [
    'example.com',
    'localhost',
    'YOUR_',
    'TODO',
    'CHANGEME',
    'placeholder',
    'foo.com',
    'test.com',
  ];

  function inspectValue(val: unknown, path: string) {
    if (typeof val === 'string') {
      const lower = val.toLowerCase();
      for (const token of disallowedTokens) {
        if (lower.includes(token.toLowerCase())) {
          errors.push(`Disallowed placeholder '${token}' found at siteConfig.${path}: "${val}"`);
        }
      }
    } else if (Array.isArray(val)) {
      val.forEach((item, idx) => inspectValue(item, `${path}[${idx}]`));
    } else if (val && typeof val === 'object') {
      Object.entries(val).forEach(([k, v]) => inspectValue(v, `${path}.${k}`));
    }
  }

  inspectValue(config, 'siteConfig');

  // Verify claims do not contain forbidden words
  const claimsText = JSON.stringify(config.claims).toLowerCase();
  if (claimsText.includes('security guard') || claimsText.includes('psara')) {
    // Only permitted if clarifying we do NOT provide it
    if (!claimsText.includes('do not provide')) {
      errors.push("Claims must not offer security guard or PSARA services.");
    }
  }
  if (claimsText.includes('police verified') || claimsText.includes('police-verified')) {
    errors.push("Claims must not state 'police verified'; use KYC/identity verification.");
  }
  if (claimsText.includes('replacement guarantee')) {
    errors.push("Claims must not use 'replacement guarantee' wording; use managed replacement workflow.");
  }

  return errors;
}

