# Legal Disclaimer

**Drift is designed exclusively for authorized security testing.**

## Authorized Use Only

You may only use Drift against systems and networks for which you have **explicit written authorization** from the system owner. Unauthorized use may violate:

- The Computer Fraud and Abuse Act (CFAA) - United States
- The Computer Misuse Act - United Kingdom
- Equivalent laws in your jurisdiction

## No Warranty

Drift is provided "AS IS" without warranty of any kind. The authors and contributors are not liable for any damages arising from use or misuse of this software.

## Responsible Disclosure

If you discover a security vulnerability in Drift itself, please report it responsibly per `SECURITY.md`. Do not exploit it.

## Scope Enforcement

Drift includes built-in scope enforcement:
- Hard-block on RFC-reserved IP ranges (10.x, 172.16.x, 192.168.x, 127.x, etc.) unless explicitly in scope
- Hard-block on .gov and .mil TLDs
- Hard-block on cloud metadata endpoints (169.254.169.254, etc.)
- All scan activity logged with actor identity, timestamp, and scope

**The presence of these controls does not substitute for your legal responsibility to obtain authorization.**
