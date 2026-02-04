# Azure App Registration Guide for Outlook MCP

To use the Outlook MCP, you need to register an application in your Microsoft 365 Tenant (Azure Portal) to get a **Client ID** and **Tenant ID**.

## 1. Register the Application

1. Go to the [Azure Portal](https://portal.azure.com/#view/Microsoft_AAD_IAM/ActiveDirectoryMenuBlade/~/RegisteredApps) (App Registrations).
2. Click **New registration**.
3. **Name**: Enter a name, e.g., `Outlook-MCP-Agent`.
4. **Supported account types**: Select **Accounts in this organizational directory only** (Single tenant).
5. **Redirect URI**:
   - Select **Public client/native (mobile & desktop)** from the dropdown.
   - Enter `http://localhost` (Using Device Code Flow usually doesn't strictly require a specific redirect URI if configured as a public client, but this is good practice).
6. Click **Register**.

## 2. Configure Authentication

1. In the app overview page, find the **Authentication** blade in the left menu.
2. Scroll down to **Advanced settings** > **Allow public client flows**.
3. Set "Enable the following mobile and desktop flows" to **Yes**.
   - _This is critical for the Device Code Flow we will use._
4. Click **Save**.

## 3. Add API Permissions

1. Go to the **API permissions** blade.
2. Click **Add a permission** > **Microsoft Graph** > **Delegated permissions**.
   - _Note: We use Delegated permissions so the agent acts AS YOU._
3. Search for and select the following permissions:
   - `User.Read` (Sign in and read user profile)
   - `Calendars.ReadWrite` (Read and write calendars)
   - `Calendars.Read.Shared` (Read calendars you have access to, e.g., AAA and BBB)
   - `People.Read` (Read your contacts/people to find AAA/BBB emails)
   - `Place.Read.All` (Read meeting rooms/places)
4. Click **Add permissions**.
5. (Optional but recommended) Click **Grant admin consent for [Your Org]** if you are the admin, to suppress consent prompts for these scopes.

## 4. Get Keys

1. Go to the **Overview** blade.
2. Copy the **Application (client) ID**.
3. Copy the **Directory (tenant) ID**.

## 5. Configure Your Environment

Create or update the `.env` file in your workspace `c:\Users\z1t\workspace\meetingMCP\.env` with:

```env
AZURE_CLIENT_ID=your_client_id_here
AZURE_TENANT_ID=your_tenant_id_here
```

(You do NOT need a Client Secret for "Public client/native" apps using Device Code Flow, which is more secure for local scripts).
