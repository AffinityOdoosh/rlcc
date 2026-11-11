# -*- coding: utf-8 -*-

import operator
import logging
# pyrefly: ignore [missing-import]
from odoo import fields, models, _
# pyrefly: ignore [missing-import]
from odoo.exceptions import UserError

_logger = logging.getLogger('move_attendance')

class move_attendance_wizard(models.TransientModel):
    _name = "move.draft.attendance.wizard"
    _description = 'Move Draft Attendance Wizard'
    
    date1 = fields.Datetime('From', required=True)
    date2 = fields.Datetime('To', required=True)
    employee_ids = fields.Many2many('hr.employee', 'move_att_employee_rel', 'employee_id', 'wiz_id')
    
    def move_confirm(self):
        self.ensure_one()
        if self.date1 and self.date2 and self.date1 > self.date2:
            raise UserError(_("The 'From' date cannot be later than the 'To' date."))

        try:
            hr_attendance_draft = self.env['hr.draft.attendance']
            hr_attendance_model = self.env['hr.attendance']
            hr_employee = self.env['hr.employee']
            employees = []
            if self.employee_ids:
                employees = self.employee_ids
            else:
                employees = hr_employee.search([])
                
            atten = {}
            all_attendances = []
            for employee in employees:
                domain = [
                    ('employee_id', '=', employee.id),
                    ('attendance_status', '!=', 'sign_none'),
                    ('moved', '=', False),
                ]
                if self.date1:
                    domain.append(('name', '>=', self.date1))
                if self.date2:
                    domain.append(('name', '<=', self.date2))

                attendance_ids = hr_attendance_draft.search(domain, order='name asc')
                if attendance_ids:
                    all_attendances += attendance_ids
                    atten[employee.id] = {}
                    for att in attendance_ids:
                        if att.date in atten[employee.id]:
                            atten[employee.id][att.date].append(att)
                        else:
                            atten[employee.id][att.date] = []
                            atten[employee.id][att.date].append(att)
                else:
                    _logger.warning('Valid Draft Attendance records not found for employee ' + str(employee.name))
                        
            if atten:
                for emp in atten:
                    created_rec = False
                    if emp:
                        employee_dic = atten[emp]
                        sorted_employee_dic = sorted(employee_dic.items(), key=operator.itemgetter(0))
                        last_action = False
                        for attendance_day in sorted_employee_dic:
                            day_dict = attendance_day[1]
                            for line in day_dict:
                                if line.attendance_status != 'sign_none':
                                    if line.attendance_status == 'sign_in':
                                        _logger.info('.....Processing CHECK IN draft record ' + str(line) + ' -- ' + str(line.attendance_status))
                                        check_in = line.name
                                        vals = {
                                                'employee_id': line.employee_id.id,
                                                'check_in': check_in,
                                                }
                                        existing_attendance = hr_attendance_model.search([('check_in', '=', str(line.name)), ('employee_id', '=', line.employee_id.id)], limit=1)
                                        if not existing_attendance:
                                            if last_action != line.attendance_status:
                                                created_rec = hr_attendance_model.create(vals)
                                                line.moved = True
                                                line.moved_to = created_rec.id
                                                _logger.info('Create Attendance ' + str(created_rec) + ' for ' + str(line.employee_id.name) + ' on ' + str(line.name))
                                        else:
                                            line.moved = True
                                            line.moved_to = existing_attendance.id
                                            _logger.info('Skipping Create Attendance because it already exists for ' + str(line.employee_id.name) + ' on ' + str(line.name))
                                                
                                    elif line.attendance_status == 'sign_out':
                                        check_out = line.name
                                        if created_rec and created_rec.employee_id.id == line.employee_id.id:
                                            created_rec.write({'check_out': check_out})
                                            line.moved = True
                                            line.moved_to = created_rec.id
                                            _logger.info('Updated ' + str(created_rec.check_in.strftime("%A")) + "'s Attendance, " + str(line.employee_id.name) + ' Checked Out at: ' + str(check_out))
                                            created_rec = False
                                        else:
                                            _logger.warning('Unable to find relevant attendance record on ' + str(line.date) + ' for Attendance, ' + str(line.employee_id.name) + ' Checked Out at: ' + str(check_out))
                                    else:
                                        raise UserError(_('Error ! Sign in (resp. Sign out) must follow Sign out (resp. Sign in) at ' + str(line.name) + ' for ' + str(line.employee_id.name)))
                                    last_action = line.attendance_status
                                else:
                                    _logger.warning('....invalid draft state ' + str(line.attendance_status) + ' -- ' + str(line))
        except Exception as e:
            raise UserError("The following error occured while moving attendances.\n\n" + str(e))
