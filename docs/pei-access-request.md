**To:** the Clerk of the Legislative Assembly of Prince Edward Island (assembly@assembly.pe.ca)
**From:** Christopher Joyce, CitizenGO
**Subject:** Automated access to the Assembly's public House records

Dear Clerk,

I am writing to ask for a way to read the Legislative Assembly's public House records automatically, at a low and polite rate.

I work at CitizenGO, where we monitor how legislatures across Canada vote and debate on a set of public-policy issues. Our monitor already reads the Journals, Votes and Proceedings, Hansard and bill texts of eight provincial legislatures and the Parliament of Canada. It does so directly from each Assembly's own website, so that every record we hold cites its official source.

Prince Edward Island is the one legislature we cannot read. Requests to the house records pages, for example https://www.assembly.pe.ca/legislative-business/house-records, are redirected to a bot-protection challenge (validate.perfdrive.com). The block applies both from our office and from the cloud servers our collector runs on. We stopped as soon as we saw the challenge. We will not try to get around it, which is why I am asking you directly.

What we would read:

- The Journals (or Votes and Proceedings), Hansard and bill texts of the current and recent General Assemblies.
- Once only, the same records back to 2010, then each week's new sittings.

How our collector behaves:

- It identifies itself honestly with the User-Agent `parl-monitor (CitizenGO parliamentary research; https://citizengo.org)`.
- It follows robots.txt and any crawl-delay you set. Elsewhere it waits several seconds between requests and never makes them in parallel.
- It fetches each record once and keeps a copy, so it does not ask for the same page twice.
- For the one-off back-reading, we are happy to work to any rate or time window you prefer, such as overnight or weekends.

Either of the following would solve it:

1. Allowlisting the User-Agent above for the house records and bill pages.
2. If that does not suit your security arrangements, a bulk copy or feed of the records, and we would collect nothing from the site at all.

If it helps, I am glad to talk this through with you or your IT provider, or to answer any questions about how the records are used.

Thank you for considering this.

Yours sincerely,

Christopher Joyce
CitizenGO
cjoyce@citizengo.net
