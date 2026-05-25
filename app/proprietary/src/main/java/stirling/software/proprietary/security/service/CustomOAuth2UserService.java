package stirling.software.proprietary.security.service;

import java.util.List;
import java.util.Map;
import java.util.Optional;

import org.springframework.security.authentication.LockedException;
import org.springframework.security.oauth2.client.oidc.userinfo.OidcUserRequest;
import org.springframework.security.oauth2.client.oidc.userinfo.OidcUserService;
import org.springframework.security.oauth2.client.registration.ClientRegistration;
import org.springframework.security.oauth2.client.userinfo.OAuth2UserService;
import org.springframework.security.oauth2.core.OAuth2AuthenticationException;
import org.springframework.security.oauth2.core.OAuth2Error;
import org.springframework.security.oauth2.core.oidc.IdTokenClaimNames;
import org.springframework.security.oauth2.core.oidc.user.DefaultOidcUser;
import org.springframework.security.oauth2.core.oidc.user.OidcUser;

import lombok.extern.slf4j.Slf4j;

import stirling.software.common.model.ApplicationProperties;
import stirling.software.common.model.enumeration.UsernameAttribute;
import stirling.software.proprietary.security.model.User;

@Slf4j
public class CustomOAuth2UserService implements OAuth2UserService<OidcUserRequest, OidcUser> {

    // Ordered fallback chain for resolving a human-readable username when the configured
    // attribute is missing from the merged ID-token + userinfo claims. ADFS commonly emits
    // 'upn' / 'unique_name' rather than 'email' on the userinfo endpoint, so we try those
    // before giving up. 'sub' is the OIDC-mandatory last resort.
    private static final List<String> USERNAME_FALLBACK_CLAIMS =
            List.of("email", "upn", "preferred_username", "unique_name", "name", "sub");

    private final OidcUserService delegate = new OidcUserService();

    private final UserService userService;

    private final LoginAttemptService loginAttemptService;

    private final ApplicationProperties.Security.OAUTH2 oauth2Properties;

    public CustomOAuth2UserService(
            ApplicationProperties.Security.OAUTH2 oauth2Properties,
            UserService userService,
            LoginAttemptService loginAttemptService) {
        this.oauth2Properties = oauth2Properties;
        this.userService = userService;
        this.loginAttemptService = loginAttemptService;
    }

    @Override
    public OidcUser loadUser(OidcUserRequest userRequest) throws OAuth2AuthenticationException {
        String configuredKey =
                UsernameAttribute.valueOf(oauth2Properties.getUseAsUsername().toUpperCase())
                        .getName();
        try {
            // Spring's DefaultOidcUser constructor calls Assert.hasText on the claim named by
            // the ClientRegistration's userNameAttributeName and throws
            // "Attribute value for '<key>' cannot be null" if that claim is absent from the
            // merged ID-token + userinfo claims. Some OIDC providers (notably ADFS) do not
            // reliably emit 'email' through both channels. Force the delegate to use 'sub'
            // (mandatory per OIDC spec) so this assertion never fires inside Spring; we then
            // resolve the real username ourselves with fallback claims.
            OidcUser user = delegate.loadUser(withSubAsNameAttribute(userRequest));

            String ssoProviderId = user.getSubject();
            String ssoProvider = userRequest.getClientRegistration().getRegistrationId();
            String username = resolveUsername(user, configuredKey);

            if (username == null) {
                log.error(
                        "OAuth2 login failed: configured useAsUsername='{}' had no value and"
                                + " no fallback claim {} matched. Provider returned claims: {}",
                        configuredKey,
                        USERNAME_FALLBACK_CLAIMS,
                        user.getAttributes().keySet());
                throw new OAuth2AuthenticationException(
                        new OAuth2Error(
                                "oauth2_missing_username_attribute",
                                "OIDC provider did not return a value for the configured username"
                                        + " attribute '"
                                        + configuredKey
                                        + "'. Available claims: "
                                        + user.getAttributes().keySet(),
                                null));
            }

            log.debug(
                    "OAuth2 login - Provider: {}, ProviderId: {}, Username: {}",
                    ssoProvider,
                    ssoProviderId,
                    username);

            Optional<User> internalUser = userService.findByUsernameIgnoreCase(username);

            if (internalUser.isPresent()) {
                String internalUsername = internalUser.get().getUsername();
                if (loginAttemptService.isBlocked(internalUsername)) {
                    throw new LockedException(
                            "The account "
                                    + internalUsername
                                    + " has been locked due to too many failed login attempts.");
                }
                if (userService.hasPassword(internalUsername)) {
                    throw new IllegalArgumentException("Password must not be null");
                }
            }

            String resolvedKey = findKeyFor(user.getAttributes(), username, configuredKey);
            return new DefaultOidcUser(
                    user.getAuthorities(),
                    userRequest.getIdToken(),
                    user.getUserInfo(),
                    resolvedKey);
        } catch (OAuth2AuthenticationException e) {
            throw e;
        } catch (IllegalArgumentException e) {
            log.error("Error loading OIDC user: {}", e.getMessage());
            throw new OAuth2AuthenticationException(new OAuth2Error(e.getMessage()), e);
        } catch (Exception e) {
            log.error("Unexpected error loading OIDC user", e);
            throw new OAuth2AuthenticationException("Unexpected error during authentication");
        }
    }

    private OidcUserRequest withSubAsNameAttribute(OidcUserRequest userRequest) {
        ClientRegistration original = userRequest.getClientRegistration();
        String currentName =
                original.getProviderDetails().getUserInfoEndpoint().getUserNameAttributeName();
        if (IdTokenClaimNames.SUB.equals(currentName)) {
            return userRequest;
        }
        ClientRegistration patched =
                ClientRegistration.withClientRegistration(original)
                        .userNameAttributeName(IdTokenClaimNames.SUB)
                        .build();
        return new OidcUserRequest(
                patched,
                userRequest.getAccessToken(),
                userRequest.getIdToken(),
                userRequest.getAdditionalParameters());
    }

    private String resolveUsername(OidcUser user, String configuredKey) {
        String fromConfigured = asNonBlankString(user.getAttribute(configuredKey));
        if (fromConfigured != null) {
            return fromConfigured;
        }
        for (String candidate : USERNAME_FALLBACK_CLAIMS) {
            if (candidate.equals(configuredKey)) {
                continue;
            }
            String value = asNonBlankString(user.getAttribute(candidate));
            if (value != null) {
                log.warn(
                        "OAuth2 login: configured useAsUsername='{}' was missing/empty; falling"
                                + " back to claim '{}'. Consider updating the IdP to emit '{}',"
                                + " or change security.oauth2.useAsUsername.",
                        configuredKey,
                        candidate,
                        configuredKey);
                return value;
            }
        }
        return null;
    }

    private String findKeyFor(Map<String, Object> attributes, String value, String preferredKey) {
        if (value.equals(asNonBlankString(attributes.get(preferredKey)))) {
            return preferredKey;
        }
        for (Map.Entry<String, Object> entry : attributes.entrySet()) {
            if (value.equals(asNonBlankString(entry.getValue()))) {
                return entry.getKey();
            }
        }
        return IdTokenClaimNames.SUB;
    }

    private static String asNonBlankString(Object value) {
        if (value instanceof String s && !s.isBlank()) {
            return s;
        }
        return null;
    }
}
