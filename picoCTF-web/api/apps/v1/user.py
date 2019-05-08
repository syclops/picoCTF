"""Endpoints related to authorization and the current user."""
from flask import jsonify
from flask_restplus import Namespace, Resource

import api.email
import api.user
from api.common import PicoException

from .schemas import (disable_account_req, login_req,
                      reset_password_confirmation_req, reset_password_req,
                      update_password_req, user_extdata_req,
                      email_verification_req)

ns = Namespace('user', description='Authentication and information about ' +
                                   'current user')


@ns.response(200, 'Success')
@ns.response(401, 'Not logged in')
@ns.route('/')
class User(Resource):
    """Get the current user or update their extdata."""

    # @require_login
    def get(self):
        """Get information about the current user."""
        return jsonify(api.user.get_user())

    # @require_login
    @ns.expect(user_extdata_req)
    def patch(self):
        """Update the current user's extdata (other fields not supported)."""
        req = user_extdata_req.parse_args(strict=True)
        api.user.update_extdata(req['extdata'])
        return jsonify({
            'success': True
        })


@ns.route('/login')
class LoginResponse(Resource):
    """Log in."""

    # @require_login
    @ns.response(200, 'Sucess')
    @ns.response(400, 'Error parsing request')
    @ns.response(401, 'Incorrect username or password')
    @ns.response(403, 'Account disabled or not yet verified')
    @ns.expect(login_req)
    def post(self):
        """Log in."""
        req = login_req.parse_args(strict=True)
        api.user.login(req['username'], req['password'])
        return jsonify({
            "success": True,
            "username": req['username']
        })


@ns.route('/logout')
class LogoutResponse(Resource):
    """Log out."""

    @ns.response(200, 'Success')
    @ns.response(401, 'Not logged in')
    def get(self):
        """Log out."""
        if not api.user.is_logged_in():
            raise PicoException(
                'There is no user currently logged in.', 401
            )
        else:
            api.user.logout()
        return jsonify({
            'success': True
        })


@ns.route('/authorize/<string:requested_role>')
class AuthorizationResponse(Resource):
    """
    Determine whether the current user has certain roles.

    Used to handle authorization in nginx.
    """

    @ns.response(200, 'User is authorized for the given role')
    @ns.response(401, 'User is not authorized for the given role')
    def get(self, requested_role):
        """Get the authorization status for the current user."""
        # Determine authorizations
        authorizations = {
            'anonymous': True,
            'user': False,
            'teacher': False,
            'admin': False
        }
        if requested_role not in authorizations:
            raise PicoException('Invalid role', 401)

        user = None
        if api.user.is_logged_in():
            user = api.user.get_user()

        if user:
            for role in ['teacher', 'admin']:
                authorizations['role'] = user['role']

        if authorizations[requested_role] is True:
            status_code = 200
        else:
            status_code = 401

        res = jsonify(authorizations)
        res.status_code = status_code
        return res


@ns.route('/disable_account')
class DisableAccountResponse(Resource):
    """Disable your user account. Requires password confirmation."""

    # @require_login
    # @check_csrf
    @ns.response(200, 'Success')
    @ns.response(401, 'Not logged in')
    @ns.response(500, 'Provided password is not correct')
    @ns.expect(disable_account_req)
    def post(self):
        """
        Disable your user account. Requires password confirmation.

        Note that this is an irreversable action.
        """
        user = api.user.get_user(include_pw_hash=True)
        req = disable_account_req.parse_args(strict=True)

        if not api.user.confirm_password(
                req['password'], user['password_hash']):
            raise PicoException('The provided password is not correct.')
        api.user.disable_account(user['uid'])
        return jsonify({
            'success': True
            })


@ns.route('/update_password')
class UpdatePasswordResponse(Resource):
    """Update your account password."""

    # @require_login
    # @check_csrf
    @ns.response(200, 'Success')
    @ns.response(400, 'Error parsing request')
    @ns.response(401, 'Not logged in')
    @ns.response(422, 'Provided password does not match')
    @ns.expect(update_password_req)
    def post(self):
        """Update your account password."""
        req = update_password_req.parse_args(strict=True)
        # @TODO refactor update_password_request()
        api.user.update_password_request(
            {
                'current-password': req['current_password'],
                'new-password': req['new_password'],
                'new-password-confirmation':
                    req['new_password_confirmation']
            }, check_current=True
        )
        return jsonify({
            'success': True
        })


@ns.route('/reset_password')
class ResetPasswordResponse(Resource):
    """Reset a user's password. Requires a password reset token."""

    @ns.response(200, 'Success')
    @ns.response(400, 'Error parsing request')
    @ns.response(422, 'Invalid token')
    @ns.expect(reset_password_confirmation_req)
    def post(self):
        """Reset a user's password. Requires a password reset token."""
        req = reset_password_confirmation_req.parse_args(strict=True)
        api.user.reset_password(req['reset_token', req['new_password'],
                                req['new_password_confirmation']])
        return jsonify({
            'success': True
        })


@ns.route('/reset_password/request')
class ResetPasswordRequestResponse(Resource):
    """Request a password reset. Does not require authentication."""

    @ns.response(200, 'Success')
    @ns.response(400, 'Error parsing request')
    @ns.response(404, 'Username not found')
    @ns.expect(reset_password_req)
    def post(self):
        """Request a password reset. Does not require authentication."""
        req = reset_password_req.parse_args(strict=True)
        api.email.request_password_reset(req['username'])
        return jsonify({
            'success': True
        })


@ns.route('/verify')
class UserVerificationResponse(Resource):
    """Verify a user's email address."""

    # @TODO
    # previously redirected to /#team-builder : /#status=verified ?
    #   max_team_size > 1
    # or / if invalid... either frontend or this will need to change


    # @require_login
    @ns.response(200, 'Success')
    @ns.response(401, 'Not logged in')
    @ns.response(422, 'Invalid token')
    @ns.expect(email_verification_req)
    def get(self):
        """Verify a user's email address."""
        req = email_verification_req.parse_args(strict=True)
        success = api.user.verify_user(req['token'])
        if not success:
            raise PicoException(
                'Invalid verification token.', 422
            )
        return jsonify({
            'success': True
        })
