import razorpay







from django.conf import settings



from django.db import transaction



from django.utils import timezone







from rest_framework import status



from rest_framework.permissions import IsAuthenticated



from rest_framework.response import Response



from rest_framework.views import APIView







from apps.bookings.models import Booking



from apps.seats.models import Seat



from apps.memberships.models import Membership







from .models import Payment



from .serializers import PaymentSerializer











class PaymentListCreateView(APIView):



    permission_classes = [IsAuthenticated]







    def get(self, request):



        payments = Payment.objects.filter(



            student=request.user



        ).select_related(



            "booking",



            "membership",



        )







        serializer = PaymentSerializer(



            payments,



            many=True,



        )







        return Response(serializer.data)







    def post(self, request):



        serializer = PaymentSerializer(



            data=request.data



        )







        if not serializer.is_valid():



            return Response(



                serializer.errors,



                status=status.HTTP_400_BAD_REQUEST,



            )







        booking = serializer.validated_data.get("booking")







        if not booking:



            return Response(



                {



                    "detail": "Booking is required for this payment endpoint."



                },



                status=status.HTTP_400_BAD_REQUEST,



            )







        if booking.student != request.user:



            return Response(



                {



                    "detail": "You can only pay for your own booking."



                },



                status=status.HTTP_403_FORBIDDEN,



            )







        if booking.status != "reserved":



            return Response(



                {



                    "detail": "This booking is not available for payment."



                },



                status=status.HTTP_400_BAD_REQUEST,



            )







        if booking.reserved_until <= timezone.now():



            return Response(



                {



                    "detail": "This booking has expired."



                },



                status=status.HTTP_400_BAD_REQUEST,



            )







        payment = serializer.save(



            student=request.user,



            status="pending",



        )







        return Response(



            PaymentSerializer(payment).data,



            status=status.HTTP_201_CREATED,



        )











class PaymentOrderCreateView(APIView):



    permission_classes = [IsAuthenticated]







    @transaction.atomic



    def post(self, request):



        booking_id = request.data.get("booking")







        if not booking_id:



            return Response(



                {



                    "detail": "Booking ID is required."



                },



                status=status.HTTP_400_BAD_REQUEST,



            )







        try:



            booking = (



                Booking.objects



                .select_related(



                    "plan",



                    "library",



                )



                .get(id=booking_id)



            )



        except Booking.DoesNotExist:



            return Response(



                {



                    "detail": "Booking not found."



                },



                status=status.HTTP_404_NOT_FOUND,



            )







        if booking.student != request.user:



            return Response(



                {



                    "detail": "You can only pay for your own booking."



                },



                status=status.HTTP_403_FORBIDDEN,



            )







        if booking.status != "reserved":



            return Response(



                {



                    "detail": "This booking is not available for payment."



                },



                status=status.HTTP_400_BAD_REQUEST,



            )







        if booking.reserved_until <= timezone.now():



            return Response(



                {



                    "detail": "This booking has expired."



                },



                status=status.HTTP_400_BAD_REQUEST,



            )







        amount = booking.plan.price







        existing_payment = (



            Payment.objects



            .filter(



                booking=booking,



                status="pending",



            )



            .first()



        )







        if existing_payment:



            return Response(



                {



                    "order_id": existing_payment.razorpay_order_id,



                    "amount": existing_payment.amount,



                    "currency": "INR",



                    "key_id": settings.RAZORPAY_KEY_ID,



                    "booking_id": booking.id,



                    "payment_id": existing_payment.id,



                },



                status=status.HTTP_200_OK,



            )







        client = razorpay.Client(



            auth=(



                settings.RAZORPAY_KEY_ID,



                settings.RAZORPAY_KEY_SECRET,



            )



        )







        razorpay_order = client.order.create(



            {



                "amount": int(amount * 100),



                "currency": "INR",



                "receipt": str(booking.id),



            }



        )







        payment = Payment.objects.create(



            student=request.user,



            booking=booking,



            membership=None,



            amount=amount,



            payment_method="razorpay",



            status="pending",



            razorpay_order_id=razorpay_order["id"],



        )







        return Response(



            {



                "order_id": razorpay_order["id"],



                "amount": payment.amount,



                "currency": "INR",



                "key_id": settings.RAZORPAY_KEY_ID,



                "booking_id": booking.id,



                "payment_id": payment.id,



            },



            status=status.HTTP_201_CREATED,



        )











class PaymentVerifyView(APIView):



    permission_classes = [IsAuthenticated]







    @transaction.atomic



    def post(self, request):



        razorpay_order_id = request.data.get(



            "razorpay_order_id"



        )







        razorpay_payment_id = request.data.get(



            "razorpay_payment_id"



        )







        razorpay_signature = request.data.get(



            "razorpay_signature"



        )







        if not razorpay_order_id:



            return Response(



                {



                    "detail": "razorpay_order_id is required."



                },



                status=status.HTTP_400_BAD_REQUEST,



            )







        if not razorpay_payment_id:



            return Response(



                {



                    "detail": "razorpay_payment_id is required."



                },



                status=status.HTTP_400_BAD_REQUEST,



            )







        if not razorpay_signature:



            return Response(



                {



                    "detail": "razorpay_signature is required."



                },



                status=status.HTTP_400_BAD_REQUEST,



            )







        try:



            payment = (



                Payment.objects



                .select_for_update()



                .select_related(



                    "booking",



                    "booking__seat",



                    "booking__plan",



                    "booking__library",



                )



                .get(



                    razorpay_order_id=razorpay_order_id



                )



            )



        except Payment.DoesNotExist:



            return Response(



                {



                    "detail": "Payment record not found."



                },



                status=status.HTTP_404_NOT_FOUND,



            )







        if payment.student != request.user:



            return Response(



                {



                    "detail": "You can only verify your own payment."



                },



                status=status.HTTP_403_FORBIDDEN,



            )







        if payment.status == "successful":



            return Response(



                {



                    "detail": "Payment is already successful."



                },



                status=status.HTTP_400_BAD_REQUEST,



            )







        booking = payment.booking







        if not booking:



            return Response(



                {



                    "detail": "This payment is not a booking payment."



                },



                status=status.HTTP_400_BAD_REQUEST,



            )







        if booking.status != "reserved":



            return Response(



                {



                    "detail": "This booking is no longer available."



                },



                status=status.HTTP_400_BAD_REQUEST,



            )







        if booking.reserved_until <= timezone.now():



            return Response(



                {



                    "detail": "This booking has expired."



                },



                status=status.HTTP_400_BAD_REQUEST,



            )







        client = razorpay.Client(



            auth=(



                settings.RAZORPAY_KEY_ID,



                settings.RAZORPAY_KEY_SECRET,



            )



        )







        try:



            client.utility.verify_payment_signature(



                {



                    "razorpay_order_id": razorpay_order_id,



                    "razorpay_payment_id": razorpay_payment_id,



                    "razorpay_signature": razorpay_signature,



                }



            )



        except razorpay.errors.SignatureVerificationError:



            payment.status = "failed"



            payment.save(



                update_fields=[



                    "status",



                    "updated_at",



                ]



            )







            return Response(



                {



                    "detail": "Invalid Razorpay payment signature."



                },



                status=status.HTTP_400_BAD_REQUEST,



            )







        seat = (



            Seat.objects



            .select_for_update()



            .get(id=booking.seat_id)



        )







        if seat.status != "reserved":



            return Response(



                {



                    "detail": "Seat is not reserved for this booking."



                },



                status=status.HTTP_400_BAD_REQUEST,



            )







        payment.status = "successful"



        payment.razorpay_payment_id = razorpay_payment_id



        payment.razorpay_signature = razorpay_signature



        payment.transaction_id = razorpay_payment_id



        payment.paid_at = timezone.now()







        payment.save(



            update_fields=[



                "status",



                "razorpay_payment_id",



                "razorpay_signature",



                "transaction_id",



                "paid_at",



                "updated_at",



            ]



        )







        booking.status = "confirmed"







        booking.save(



            update_fields=[



                "status",



                "updated_at",



            ]



        )







        seat.status = "occupied"







        seat.save(



            update_fields=[



                "status",



                "updated_at",



            ]



        )







        start_date = timezone.localdate()







        next_due_date = (



            start_date



            + timezone.timedelta(



                days=booking.plan.duration_days



            )



        )







        membership = Membership.objects.create(



            student=request.user,



            library=booking.library,



            plan=booking.plan,



            seat=booking.seat,



            start_date=start_date,



            next_due_date=next_due_date,



            status="active",



        )







        return Response(



            {



                "message": "Payment verified successfully.",



                "payment": PaymentSerializer(payment).data,



                "booking_status": booking.status,



                "seat_status": seat.status,



                "membership_id": membership.id,



                "membership_status": membership.status,



                "next_due_date": membership.next_due_date,



            },



            status=status.HTTP_200_OK,



        )











class RenewalPaymentOrderCreateView(APIView):



    permission_classes = [IsAuthenticated]



    @transaction.atomic

    def post(self, request):

        membership_id = request.data.get("membership")



        if not membership_id:

            return Response(

                {"detail": "Membership ID is required."},

                status=status.HTTP_400_BAD_REQUEST,

            )




        try:

            membership = (

                Membership.objects

                .select_for_update()

                .select_related("plan", "library")

                .get(id=membership_id)

            )

        except Membership.DoesNotExist:


            return Response(

                {"detail": "Membership not found."},

                status=status.HTTP_404_NOT_FOUND,

            )


        if membership.student_id != request.user.id:

            return Response(

                {"detail": "You can only renew your own membership."},

                status=status.HTTP_403_FORBIDDEN,

            )



        if membership.status == "archived":

            return Response(

                {"detail": "Archived membership cannot be renewed."},

                status=status.HTTP_400_BAD_REQUEST,

            )



        amount = membership.plan.price



        client = razorpay.Client(

            auth=(

                settings.RAZORPAY_KEY_ID,

                settings.RAZORPAY_KEY_SECRET,

            )

        )



        existing_payment = (

            Payment.objects

            .filter(membership=membership, status="pending")

            .order_by("-created_at")

            .first()

        )



        if existing_payment:

            try:

                existing_order = client.order.fetch(

                    existing_payment.razorpay_order_id

                )

                existing_order_status = existing_order.get("status")

            except Exception:

                existing_order_status = None



            if existing_order_status in {"created", "attempted"}:

                return Response(

                    {

                        "order_id": existing_payment.razorpay_order_id,

                        "amount": existing_payment.amount,

                        "currency": "INR",

                        "key_id": settings.RAZORPAY_KEY_ID,

                        "membership_id": membership.id,

                        "payment_id": existing_payment.id,

                    },

                    status=status.HTTP_200_OK,

                )



            # Recover a payment that Razorpay marked paid but whose

            # frontend verification callback did not reach Django.

            if existing_order_status == "paid":

                try:

                    order_payments = client.order.payments(

                        existing_payment.razorpay_order_id

                    )



                    paid_payment = next(

                        (

                            item

                            for item in order_payments.get("items", [])

                            if item.get("status") == "captured"

                        ),

                        None,

                    )



                    if not paid_payment:

                        return Response(

                            {

                                "detail": (

                                    "Razorpay reports this order as paid, "

                                    "but no captured payment was found. "

                                    "Please contact support."

                                )

                            },

                            status=status.HTTP_400_BAD_REQUEST,

                        )



                    existing_payment.status = "successful"

                    existing_payment.razorpay_payment_id = paid_payment.get("id")

                    existing_payment.transaction_id = paid_payment.get("id")

                    existing_payment.paid_at = timezone.now()



                    existing_payment.save(

                        update_fields=[

                            "status",

                            "razorpay_payment_id",

                            "transaction_id",

                            "paid_at",

                            "updated_at",

                        ]

                    )



                    today = timezone.localdate()



                    membership.start_date = today

                    membership.next_due_date = (

                        today

                        + timezone.timedelta(

                            days=membership.plan.duration_days

                        )

                    )

                    membership.status = "active"



                    membership.save(

                        update_fields=[

                            "start_date",

                            "next_due_date",

                            "status",

                            "updated_at",

                        ]

                    )



                    return Response(

                        {

                            "detail": (

                                "The previous renewal payment was already "

                                "completed and your membership has been updated."

                            ),

                            "payment_id": existing_payment.id,

                            "membership_id": membership.id,

                            "membership_status": membership.status,

                            "start_date": membership.start_date,

                            "next_due_date": membership.next_due_date,

                        },

                        status=status.HTTP_200_OK,

                    )



                except Exception:

                    return Response(

                        {

                            "detail": (

                                "Razorpay reports this renewal order as paid, "

                                "but it could not be reconciled automatically. "

                                "Please contact support."

                            )

                        },

                        status=status.HTTP_400_BAD_REQUEST,

                    )



            # The local payment is pending but its Razorpay order is no

            # longer usable. Mark it failed and create a fresh order.

            existing_payment.status = "failed"

            existing_payment.save(

                update_fields=["status", "updated_at"]

            )



        razorpay_order = client.order.create(

            {

                "amount": int(amount * 100),

                "currency": "INR",

                "receipt": (

                    f"renewal-{str(membership.id).replace('-', '')[:16]}-{int(timezone.now().timestamp())}"

                ),

            }

        )



        payment = Payment.objects.create(

            student=request.user,

            booking=None,

            membership=membership,

            amount=amount,

            payment_method="razorpay",

            status="pending",

            razorpay_order_id=razorpay_order["id"],

        )



        return Response(

            {

                "order_id": razorpay_order["id"],

                "amount": payment.amount,

                "currency": "INR",

                "key_id": settings.RAZORPAY_KEY_ID,

                "membership_id": membership.id,

                "payment_id": payment.id,

            },

            status=status.HTTP_201_CREATED,

        )





class RenewalPaymentVerifyView(APIView):



    permission_classes = [IsAuthenticated]



    @transaction.atomic

    def post(self, request):

        razorpay_order_id = request.data.get("razorpay_order_id")

        razorpay_payment_id = request.data.get("razorpay_payment_id")

        razorpay_signature = request.data.get("razorpay_signature")



        if not razorpay_order_id:

            return Response(

                {"detail": "razorpay_order_id is required."},

                status=status.HTTP_400_BAD_REQUEST,

            )



        if not razorpay_payment_id:

            return Response(

                {"detail": "razorpay_payment_id is required."},

                status=status.HTTP_400_BAD_REQUEST,

            )



        if not razorpay_signature:

            return Response(

                {"detail": "razorpay_signature is required."},

                status=status.HTTP_400_BAD_REQUEST,

            )



        try:
            # Lock the Payment row by itself. Payment.membership is nullable,
            # so PostgreSQL cannot apply FOR UPDATE to the nullable side of
            # the OUTER JOIN produced by select_related("membership").
            payment = (
                Payment.objects
                .select_for_update()
                .get(razorpay_order_id=razorpay_order_id)
            )
        except Payment.DoesNotExist:
            return Response(
                {"detail": "Payment record not found."},
                status=status.HTTP_404_NOT_FOUND,
            )



        if payment.student_id != request.user.id:

            return Response(

                {"detail": "You can only verify your own payment."},

                status=status.HTTP_403_FORBIDDEN,

            )



        if not payment.membership:

            return Response(

                {"detail": "This payment is not a renewal payment."},

                status=status.HTTP_400_BAD_REQUEST,

            )



        if payment.status == "successful":

            return Response(

                {"detail": "Payment is already successful."},

                status=status.HTTP_400_BAD_REQUEST,

            )



        try:
            membership = (
                Membership.objects
                .select_for_update()
                .select_related("plan", "library")
                .get(id=payment.membership_id)
            )
        except Membership.DoesNotExist:
            return Response(
                {"detail": "Membership not found for this payment."},
                status=status.HTTP_404_NOT_FOUND,
            )

        if membership.student_id != request.user.id:

            return Response(

                {"detail": "You can only renew your own membership."},

                status=status.HTTP_403_FORBIDDEN,

            )



        if membership.status == "archived":

            return Response(

                {"detail": "Archived membership cannot be renewed."},

                status=status.HTTP_400_BAD_REQUEST,

            )



        client = razorpay.Client(

            auth=(

                settings.RAZORPAY_KEY_ID,

                settings.RAZORPAY_KEY_SECRET,

            )

        )



        try:

            client.utility.verify_payment_signature(

                {

                    "razorpay_order_id": razorpay_order_id,

                    "razorpay_payment_id": razorpay_payment_id,

                    "razorpay_signature": razorpay_signature,

                }

            )

        except razorpay.errors.SignatureVerificationError:

            payment.status = "failed"

            payment.save(

                update_fields=["status", "updated_at"]

            )



            return Response(

                {"detail": "Invalid Razorpay payment signature."},

                status=status.HTTP_400_BAD_REQUEST,

            )



        payment.status = "successful"

        payment.razorpay_payment_id = razorpay_payment_id

        payment.razorpay_signature = razorpay_signature

        payment.transaction_id = razorpay_payment_id

        payment.paid_at = timezone.now()



        payment.save(

            update_fields=[

                "status",

                "razorpay_payment_id",

                "razorpay_signature",

                "transaction_id",

                "paid_at",

                "updated_at",

            ]

        )



        # A renewal starts a new membership period from today.

        today = timezone.localdate()



        membership.start_date = today

        membership.next_due_date = (

            today

            + timezone.timedelta(

                days=membership.plan.duration_days

            )

        )

        membership.status = "active"



        membership.save(

            update_fields=[

                "start_date",

                "next_due_date",

                "status",

                "updated_at",

            ]

        )



        return Response(

            {

                "message": "Membership renewed successfully.",

                "payment": PaymentSerializer(payment).data,

                "membership_id": membership.id,

                "membership_status": membership.status,

                "start_date": membership.start_date,

                "next_due_date": membership.next_due_date,

            },

            status=status.HTTP_200_OK,

        )





class PaymentSuccessView(APIView):



    """



    Temporary test endpoint.







    This endpoint simulates a successful payment.







    Real Razorpay payments should use PaymentVerifyView.



    """







    permission_classes = [IsAuthenticated]







    @transaction.atomic



    def post(self, request, payment_id):



        payment = (



            Payment.objects



            .select_for_update()



            .select_related(



                "booking",



                "booking__seat",



                "booking__plan",



                "booking__library",



            )



            .get(id=payment_id)



        )







        if payment.student != request.user:



            return Response(



                {



                    "detail": "You can only confirm your own payment."



                },



                status=status.HTTP_403_FORBIDDEN,



            )







        if payment.status == "successful":



            return Response(



                {



                    "detail": "Payment is already successful."



                },



                status=status.HTTP_400_BAD_REQUEST,



            )







        booking = payment.booking







        if not booking:



            return Response(



                {



                    "detail": "This endpoint only supports booking payments."



                },



                status=status.HTTP_400_BAD_REQUEST,



            )







        if booking.status != "reserved":



            return Response(



                {



                    "detail": "This booking is no longer available."



                },



                status=status.HTTP_400_BAD_REQUEST,



            )







        if booking.reserved_until <= timezone.now():



            return Response(



                {



                    "detail": "This booking has expired."



                },



                status=status.HTTP_400_BAD_REQUEST,



            )







        seat = (



            Seat.objects



            .select_for_update()



            .get(id=booking.seat_id)



        )







        if seat.status != "reserved":



            return Response(



                {



                    "detail": "Seat is not reserved for this booking."



                },



                status=status.HTTP_400_BAD_REQUEST,



            )







        payment.status = "successful"



        payment.transaction_id = f"TEST-{payment.id}"



        payment.paid_at = timezone.now()







        payment.save(



            update_fields=[



                "status",



                "transaction_id",



                "paid_at",



                "updated_at",



            ]



        )







        booking.status = "confirmed"







        booking.save(



            update_fields=[



                "status",



                "updated_at",



            ]



        )







        seat.status = "occupied"







        seat.save(



            update_fields=[



                "status",



                "updated_at",



            ]



        )







        start_date = timezone.localdate()







        next_due_date = (



            start_date



            + timezone.timedelta(



                days=booking.plan.duration_days



            )



        )







        membership = Membership.objects.create(



            student=request.user,



            library=booking.library,



            plan=booking.plan,



            seat=booking.seat,



            start_date=start_date,



            next_due_date=next_due_date,



            status="active",



        )







        return Response(



            {



                "message": "Test payment successful.",



                "payment": PaymentSerializer(payment).data,



                "booking_status": booking.status,



                "seat_status": seat.status,



                "membership_id": membership.id,



                "membership_status": membership.status,



                "next_due_date": membership.next_due_date,



            },



            status=status.HTTP_200_OK,



        
        )
